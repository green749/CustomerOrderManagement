import pytest
from datetime import date, timedelta
from app.models.auth import User
from app.models.business import FactCustomerOrder, DimCustomer, DimProduct
from app.models.workflow import CommitmentProposal, AuditLog
from app.services.auth_service import hash_password, create_access_token
from app.services.workflow_service import WorkflowService
from app.repositories.order_repo import OrderRepository


def test_commitment_proposal_creation_and_revision_increment(client, auth_headers, db_session):
    """
    Test that creating commitment proposals increments revision
    and records immutable audit log rows.
    """
    order_id = "CO-000001"
    
    # 1. Create Proposal 1 (revision 1)
    res1 = client.post(
        f"/api/orders/{order_id}/commitment-proposals",
        json={
            "proposed_date": "2026-11-20",
            "recommended_by": "agent",
            "reasons": ["Supplier transit buffer", "Limiting material shortfall"],
        },
        headers=auth_headers,
    )
    assert res1.status_code == 201
    p1 = res1.json()
    assert p1["customer_order_id"] == order_id
    assert p1["status"] == "PENDING"
    assert p1["revision"] >= 1
    rev1 = p1["revision"]

    # 2. Create Proposal 2 (should increment revision)
    res2 = client.post(
        f"/api/orders/{order_id}/commitment-proposals",
        json={
            "proposed_date": "2026-11-25",
            "recommended_by": "user",
            "reasons": ["Customer request update"],
        },
        headers=auth_headers,
    )
    assert res2.status_code == 201
    p2 = res2.json()
    assert p2["revision"] == rev1 + 1
    assert p2["status"] == "PENDING"

    # Verify audit log recorded
    logs = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity == "commitment_proposal", AuditLog.action == "CREATE_PROPOSAL")
        .all()
    )
    assert len(logs) >= 2


def test_approval_rejects_stale_revision(client, auth_headers, db_session):
    """
    Test that attempting to approve a stale revision (an older revision when a newer one exists)
    is rejected with 400 Bad Request, while the latest revision can be approved.
    """
    order_id = "CO-000002"
    admin = db_session.query(User).filter(User.role == "admin").first()

    # Create revision 1
    prop1 = WorkflowService.create_commitment_proposal(
        db=db_session,
        customer_order_id=order_id,
        user=admin,
        proposed_date=date(2026, 11, 15),
        recommended_by="agent",
        reasons=["Initial proposal"],
    )

    # Create revision 2
    prop2 = WorkflowService.create_commitment_proposal(
        db=db_session,
        customer_order_id=order_id,
        user=admin,
        proposed_date=date(2026, 11, 22),
        recommended_by="agent",
        reasons=["Updated feasible promise"],
    )

    assert prop2.revision > prop1.revision

    # Attempting to approve revision 1 MUST fail (stale revision)
    res_stale = client.post(
        f"/api/commitment-proposals/{prop1.id}/approve",
        json={"decision_note": "Attempting to approve stale proposal"},
        headers=auth_headers,
    )
    assert res_stale.status_code == 400
    stale_err = str(res_stale.json().get("error") or res_stale.json().get("detail", "")).lower()
    assert "stale revision" in stale_err

    # Approving revision 2 MUST succeed
    res_approve = client.post(
        f"/api/commitment-proposals/{prop2.id}/approve",
        json={"decision_note": "Approved by commercial manager"},
        headers=auth_headers,
    )
    assert res_approve.status_code == 200
    approved_data = res_approve.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["decision_note"] == "Approved by commercial manager"

    # Verify order view reflects approved promise date
    order_res = client.get(f"/api/orders/{order_id}", headers=auth_headers)
    assert order_res.status_code == 200
    assert order_res.json()["approved_promise_date"] == "2026-11-22"


def test_role_enforcement_operator_cannot_approve(client, db_session):
    """
    Test that an operator can create proposals and view them,
    but gets 403 Forbidden when attempting to approve or reject.
    Manager / Admin can approve.
    """
    # 1. Setup operator user
    operator = db_session.query(User).filter(User.email == "operator_test@manufacturing.com").first()
    if not operator:
        op_test_pwd = os.getenv("OPERATOR_PASSWORD", "")
        operator = User(
            email="operator_test@manufacturing.com",
            hashed_password=hash_password(op_test_pwd),
            full_name="Test Operator",
            role="operator",
            is_active=True,
        )
        db_session.add(operator)
        db_session.commit()
        db_session.refresh(operator)

    # Manager user
    manager = db_session.query(User).filter(User.role == "manager").first()

    op_token = create_access_token(operator)
    mgr_token = create_access_token(manager)
    op_headers = {"Authorization": f"Bearer {op_token}"}
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    order_id = "CO-000003"

    # Operator creates proposal -> Allowed (201)
    res_create = client.post(
        f"/api/orders/{order_id}/commitment-proposals",
        json={
            "proposed_date": "2026-11-28",
            "recommended_by": "agent",
            "reasons": ["Automated promise review"],
        },
        headers=op_headers,
    )
    assert res_create.status_code == 201
    prop_id = res_create.json()["id"]

    # Operator tries to approve -> Forbidden (403)
    res_op_approve = client.post(
        f"/api/commitment-proposals/{prop_id}/approve",
        json={"decision_note": "Operator trying to sign off"},
        headers=op_headers,
    )
    assert res_op_approve.status_code == 403

    # Operator tries to reject -> Forbidden (403)
    res_op_reject = client.post(
        f"/api/commitment-proposals/{prop_id}/reject",
        json={"decision_note": "Operator trying to reject"},
        headers=op_headers,
    )
    assert res_op_reject.status_code == 403

    # Manager approves -> Allowed (200)
    res_mgr_approve = client.post(
        f"/api/commitment-proposals/{prop_id}/approve",
        json={"decision_note": "Managerial signoff"},
        headers=mgr_headers,
    )
    assert res_mgr_approve.status_code == 200
    assert res_mgr_approve.json()["status"] == "APPROVED"


def test_customer_scope_data_segregation(client, db_session):
    """
    Test data segregation: a scoped user can only see orders for customers
    specified in their customer_scope. Orders belonging to other customers are inaccessible.
    """
    # Create a user scoped strictly to customer CUS-001
    scoped_user = db_session.query(User).filter(User.email == "scoped_user@manufacturing.com").first()
    if not scoped_user:
        scoped_user = User(
            email="scoped_user@manufacturing.com",
            hashed_password=hash_password("ScopedPass123!"),
            full_name="Scoped Key Account Rep",
            role="operator",
            customer_scope=["CUS-001"],
            is_active=True,
        )
        db_session.add(scoped_user)
        db_session.commit()
        db_session.refresh(scoped_user)
    else:
        scoped_user.customer_scope = ["CUS-001"]
        db_session.commit()

    token = create_access_token(scoped_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Query orders list
    res = client.get("/api/orders?page=1&page_size=50", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0
    # Every returned order MUST belong to CUS-001
    for o in items:
        assert o["customer_id"] == "CUS-001"

    # Find an order not belonging to CUS-001
    other_order = (
        db_session.query(FactCustomerOrder)
        .filter(FactCustomerOrder.customer_id != "CUS-001")
        .first()
    )
    if other_order:
        # Accessing other customer order directly must be blocked (404 / not accessible)
        res_other = client.get(f"/api/orders/{other_order.customer_order_id}", headers=headers)
        assert res_other.status_code == 404
