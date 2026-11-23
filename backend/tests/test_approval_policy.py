import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.config import settings
from app.models.auth import User
from app.models.business import DimCustomer, FactCustomerOrder
from app.models.workflow import (
    OrderAssessment,
    DepartmentReadiness,
    CommitmentProposal,
    OrderMonitoringRecord,
    AuditLog,
)
from app.services.approval_policy_service import (
    ApprovalPolicyService,
    evaluate,
    pause_agent,
    resume_agent,
    is_agent_paused,
    get_or_create_policy_engine_user,
)
from app.services.feasibility_service import FeasibilityService
from app.services.workflow_service import WorkflowService
from app.services.intake_service import get_or_create_system_user


def test_auto_approve_when_all_conditions_hold(db_session, test_user, monkeypatch):
    """
    Test that automatic approval from Agent 2 has been permanently removed:
    Even when all feasibility criteria are FEASIBLE and confidence is HIGH,
    the proposal remains in PENDING status for mandatory human approval.
    """
    customer = db_session.query(DimCustomer).filter(DimCustomer.customer_id == "CUS-001").first()
    assert customer.manual_review_required is False

    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=30)

    # Order qty 20 * 15000 = 300,000 INR
    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=20,
        requested_delivery_date=req_date,
        user=test_user,
        unit_price_inr=15000.0,
        submit_for_approval=True,
        as_of_date=ref_date,
    )

    assert assessment.id is not None
    assert assessment.overall_status in ["FEASIBLE", "FEASIBLE_WITH_RISKS"]
    proposal = assessment.proposal
    assert proposal is not None
    # Must strictly be PENDING requiring human approval
    assert proposal.status == "PENDING"
    assert proposal.decided_by is None

    # Evaluate against policy returns NEEDS_HUMAN
    eval_res = evaluate(proposal, assessment, customer, db=db_session)
    assert eval_res["decision"] == "NEEDS_HUMAN"


def test_rule_blocks_on_non_feasible_or_low_confidence(db_session):
    """Verify that overall_status != FEASIBLE or confidence != HIGH blocks auto-approval."""
    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-001",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=1,
    )
    # Non-feasible status
    asm_at_risk = OrderAssessment(
        assessment_id="ASM-NON-FEASIBLE",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="AT_RISK",
        confidence_level="HIGH",
        created_by=1,
    )
    customer = DimCustomer(customer_id="CUS-001", customer_name="Test Cust", manual_review_required=False)

    res1 = evaluate(proposal, asm_at_risk, customer, db=db_session)
    assert res1["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res1["reasons"])

    # Low confidence
    asm_low_conf = OrderAssessment(
        assessment_id="ASM-LOW-CONF",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="LOW",
        created_by=1,
    )
    res2 = evaluate(proposal, asm_low_conf, customer, db=db_session)
    assert res2["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res2["reasons"])


def test_rule_blocks_on_order_value_exceeded(db_session, monkeypatch):
    """Verify that order value > AUTO_APPROVE_MAX_VALUE_INR blocks auto-approval."""
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")
    monkeypatch.setenv("AUTO_APPROVE_MAX_VALUE_INR", "500000")

    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-VAL",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=1,
    )
    # 50 units * 15,000 = 750,000 INR (> 500,000)
    asm_high_val = OrderAssessment(
        assessment_id="ASM-HIGH-VAL",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=50,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        created_by=1,
    )
    customer = DimCustomer(customer_id="CUS-001", customer_name="Test Cust", manual_review_required=False)

    res = evaluate(proposal, asm_high_val, customer, db=db_session)
    assert res["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res["reasons"])


def test_rule_blocks_on_department_blocker_or_agent_disagreement(db_session, monkeypatch):
    """Verify that blocked departments or agent_disagreement blocks auto-approval."""
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")

    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-BLOCK",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=1,
    )
    customer = DimCustomer(customer_id="CUS-001", customer_name="Test Cust", manual_review_required=False)

    # 1. Agent disagreement
    asm_disagreement = OrderAssessment(
        assessment_id="ASM-DISAGREE",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        agent_disagreement=True,
        created_by=1,
    )
    res_dis = evaluate(proposal, asm_disagreement, customer, db=db_session)
    assert res_dis["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res_dis["reasons"])

    # 2. Department blocker
    asm_dept_blocked = OrderAssessment(
        assessment_id="ASM-DEPT-BLOCK",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        agent_disagreement=False,
        created_by=1,
    )
    asm_dept_blocked.readiness_records = [
        DepartmentReadiness(department="MMS", readiness_status="BLOCKED"),
    ]
    res_dept = evaluate(proposal, asm_dept_blocked, customer, db=db_session)
    assert res_dept["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res_dept["reasons"])


def test_rule_blocks_on_proposed_date_later_than_requested(db_session, monkeypatch):
    """Verify that proposed_date > requested_delivery_date blocks auto-approval."""
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")

    # Proposed date is 2026-08-20, but customer requested 2026-08-15
    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-LATE",
        proposed_date=date(2026, 8, 20),
        status="PENDING",
        created_by=1,
    )
    asm = OrderAssessment(
        assessment_id="ASM-LATE",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        created_by=1,
    )
    customer = DimCustomer(customer_id="CUS-001", customer_name="Test Cust", manual_review_required=False)

    res = evaluate(proposal, asm, customer, db=db_session)
    assert res["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res["reasons"])


def test_rule_blocks_on_customer_manual_review_required(db_session, monkeypatch):
    """Verify that manual_review_required == True on DimCustomer blocks auto-approval."""
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")

    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-CUST",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=1,
    )
    asm = OrderAssessment(
        assessment_id="ASM-CUST",
        customer_id="CUS-REVIEW",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        created_by=1,
    )
    customer = DimCustomer(
        customer_id="CUS-REVIEW",
        customer_name="High Risk Customer",
        country="India",
        segment="Enterprise",
        service_level="SLA-95",
        preferred_carrier="DHL",
        manual_review_required=True,
    )

    res = evaluate(proposal, asm, customer, db=db_session)
    assert res["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res["reasons"])


def test_daily_cap_blocks_auto_approval(db_session, monkeypatch):
    """Verify that exceeding AUTO_APPROVE_MAX_PER_DAY blocks further auto-approvals."""
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")
    monkeypatch.setenv("AUTO_APPROVE_MAX_PER_DAY", "2")

    policy_user = get_or_create_policy_engine_user(db_session)

    # Seed 2 auto-approved proposals today
    now = datetime.now(timezone.utc)
    for i in range(2):
        p = CommitmentProposal(
            customer_order_id=f"CO-CAP-{i}",
            proposed_date=date(2026, 8, 10),
            status="APPROVED",
            decided_by=policy_user.id,
            decided_at=now,
            decision_note="Auto-approved by policy: seeded quota fill",
            created_by=1,
        )
        db_session.add(p)
    db_session.commit()

    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-CAP",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=1,
    )
    asm = OrderAssessment(
        assessment_id="ASM-CAP",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        created_by=1,
    )
    customer = DimCustomer(customer_id="CUS-001", customer_name="Test Cust", manual_review_required=False)

    res = evaluate(proposal, asm, customer, db=db_session)
    assert res["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res["reasons"])


def test_kill_switch_blocks_auto_approval(db_session, monkeypatch):
    """Verify that pausing the policy agent via kill switch blocks auto-approval."""
    monkeypatch.setenv("AUTO_APPROVE_ENABLED", "true")

    pause_agent("policy-engine", reason="Maintenance window")
    assert is_agent_paused("policy-engine") is True

    proposal = CommitmentProposal(
        customer_order_id="TEST-CO-KILL",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=1,
    )
    asm = OrderAssessment(
        assessment_id="ASM-KILL",
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=10,
        unit_price_inr=Decimal("15000.00"),
        requested_delivery_date=date(2026, 8, 15),
        overall_status="FEASIBLE",
        confidence_level="HIGH",
        created_by=1,
    )
    customer = DimCustomer(customer_id="CUS-001", customer_name="Test Cust", manual_review_required=False)

    res = evaluate(proposal, asm, customer, db=db_session)
    assert res["decision"] == "NEEDS_HUMAN"
    assert any("human" in r.lower() or "disabled" in r.lower() for r in res["reasons"])

    # Resume agent
    resume_agent("policy-engine")
    assert is_agent_paused("policy-engine") is False


def test_admin_kill_switch_endpoints(client, auth_headers, demo_headers):
    """Test POST /api/admin/agents/{agent}/pause and /resume endpoints."""
    # 1. Non-admin user gets 403 Forbidden
    res_forbidden = client.post("/api/admin/agents/policy-engine/pause", headers=demo_headers)
    assert res_forbidden.status_code == 403

    # 2. Admin pauses policy-engine
    res_pause = client.post(
        "/api/admin/agents/policy-engine/pause",
        json={"reason": "Emergency risk containment"},
        headers=auth_headers,
    )
    assert res_pause.status_code == 200
    data_pause = res_pause.json()
    assert data_pause["status"] == "PAUSED"
    assert is_agent_paused("policy-engine") is True

    # 3. Check status endpoint
    res_status = client.get("/api/admin/agents/policy-engine/status", headers=auth_headers)
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "PAUSED"

    # 4. Admin resumes policy-engine
    res_resume = client.post("/api/admin/agents/policy-engine/resume", headers=auth_headers)
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "ACTIVE"
    assert is_agent_paused("policy-engine") is False


def test_monitoring_activates_on_auto_approve(db_session, test_user, monkeypatch):
    """Verify that Agent 2 leaves proposal in PENDING, and subsequent human approval activates monitoring."""
    customer = db_session.query(DimCustomer).filter(DimCustomer.customer_id == "CUS-001").first()
    assert customer.manual_review_required is False

    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=30)

    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=15,
        requested_delivery_date=req_date,
        user=test_user,
        unit_price_inr=14500.0,
        submit_for_approval=True,
        as_of_date=ref_date,
    )

    # Proposal is in PENDING awaiting human review
    assert assessment.proposal.status == "PENDING"
    order_id = assessment.proposal.customer_order_id

    # Human manager reviews and approves
    approved_prop = WorkflowService.approve_proposal(
        db=db_session,
        proposal_id=assessment.proposal.id,
        user=test_user,
        decision_note="Human commercial review approved.",
    )
    assert approved_prop.status == "APPROVED"

    # Verify monitoring record created and ACTIVE
    mon_rec = db_session.query(OrderMonitoringRecord).filter(
        OrderMonitoringRecord.customer_order_id == order_id
    ).first()
    assert mon_rec is not None
    assert mon_rec.status == "ACTIVE"
    assert mon_rec.approved_delivery_date == assessment.proposal.proposed_date


def test_segregation_of_duties_maintained(db_session):
    """
    Verify that:
    1. 'policy-engine' and 'agent2-system' are distinct users.
    2. Creator cannot approve their own proposal unless administrator.
    """
    agent2_user = get_or_create_system_user(db_session, "agent2-system")
    policy_user = get_or_create_policy_engine_user(db_session)

    assert agent2_user.id != policy_user.id
    assert agent2_user.role != policy_user.role

    # Proposal created by agent2-system
    proposal = CommitmentProposal(
        customer_order_id="PRE-DUTIES-001",
        proposed_date=date(2026, 8, 10),
        status="PENDING",
        created_by=agent2_user.id,
    )
    db_session.add(proposal)
    db_session.commit()

    # Agent 2 trying to approve its own proposal must fail segregation of duties
    with pytest.raises(ValueError, match="Segregation of duties violation"):
        WorkflowService.approve_proposal(db_session, proposal.id, user=agent2_user)

    # Policy engine approving proposal created by agent2 succeeds
    approved = WorkflowService.approve_proposal(db_session, proposal.id, user=policy_user, decision_note="Auto-approved")
    assert approved.status == "APPROVED"
    assert approved.decided_by == policy_user.id
