from datetime import date, timedelta
from decimal import Decimal
import pytest
from app.models.business import DimCustomer, DimProduct, DimPlant, FactCustomerOrder
from app.models.workflow import OrderAssessment, DepartmentReadiness, CommitmentProposal
from app.services.feasibility_service import FeasibilityService


def test_agent2_fully_feasible_order(db_session, test_user):
    """
    Test Agent 2 assessing an achievable order with valid customer, product,
    materials in stock, and ample lead time.
    """
    ref_date = date(2026, 8, 1)
    requested_date = ref_date + timedelta(days=25)

    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=100,
        requested_delivery_date=requested_date,
        user=test_user,
        unit_price_inr=19000.0,
        submit_for_approval=True,
        as_of_date=ref_date,
    )

    assert assessment.id is not None
    assert assessment.customer_id == "CUS-001"
    assert assessment.product_id == "SPH-A15-128"
    assert assessment.overall_status in ["FEASIBLE", "FEASIBLE_WITH_RISKS"]
    assert assessment.estimated_delivery_date is not None
    assert assessment.proposal_id is not None

    # Check that all 7 departments were evaluated
    depts = {r.department: r.readiness_status for r in assessment.readiness_records}
    expected_depts = {"ERP", "MMS", "MES", "WMS", "QMS", "TMS", "PLM"}
    assert set(depts.keys()) == expected_depts

    # ERP, MMS, MES, TMS, PLM should be READY
    assert depts["ERP"] == "READY"
    assert depts["MMS"] == "READY"
    assert depts["MES"] == "READY"
    assert depts["TMS"] == "READY"
    assert depts["PLM"] == "READY"

    # Verify linked proposal is in PENDING status (not self-approved)
    proposal = db_session.query(CommitmentProposal).filter(CommitmentProposal.id == assessment.proposal_id).first()
    assert proposal is not None
    assert proposal.status == "PENDING"
    assert proposal.proposed_date == assessment.estimated_delivery_date


def test_agent2_invalid_customer_blocked(db_session, test_user):
    """Test Agent 2 handles invalid customer by flagging ERP as BLOCKED."""
    ref_date = date(2026, 8, 1)
    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-NONEXISTENT",
        product_id="SPH-A15-128",
        order_qty=50,
        requested_delivery_date=ref_date + timedelta(days=15),
        user=test_user,
        as_of_date=ref_date,
    )

    assert assessment.overall_status == "NOT_FEASIBLE"
    assert assessment.estimated_delivery_date is None

    erp = next((r for r in assessment.readiness_records if r.department == "ERP"), None)
    assert erp is not None
    assert erp.readiness_status == "BLOCKED"
    assert "not found in master" in erp.identified_issue


def test_agent2_unknown_product_insufficient_data(db_session, test_user):
    """Test Agent 2 handles unmapped BOM product as INSUFFICIENT_DATA or BLOCKED."""
    ref_date = date(2026, 8, 1)
    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-UNMAPPED-999",
        order_qty=50,
        requested_delivery_date=ref_date + timedelta(days=20),
        user=test_user,
        as_of_date=ref_date,
    )

    assert assessment.overall_status in ["NOT_FEASIBLE", "INSUFFICIENT_DATA"]
    wms = next((r for r in assessment.readiness_records if r.department == "WMS"), None)
    assert wms is not None
    assert wms.readiness_status == "INSUFFICIENT_DATA"


def test_agent2_material_shortage_calculation(db_session, test_user):
    """
    Test Agent 2 detects material shortage when requesting massive batch
    exceeding available snapshot stock, computing realistic replenishment lead time.
    """
    ref_date = date(2026, 8, 1)
    # 50,000 units requires more stock than on hand
    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=50000,
        requested_delivery_date=ref_date + timedelta(days=5),  # very tight 5 days
        user=test_user,
        as_of_date=ref_date,
    )

    wms = next((r for r in assessment.readiness_records if r.department == "WMS"), None)
    assert wms is not None
    assert wms.readiness_status == "PARTIALLY_READY"
    assert "Raw material shortage identified" in wms.identified_issue
    assert wms.estimated_delay_days > 0

    # Since lead time + production exceeds 5 days requested, overall status is NOT_FEASIBLE or AT_RISK
    assert assessment.overall_status in ["AT_RISK", "NOT_FEASIBLE"]
    assert assessment.days_variance > 0
