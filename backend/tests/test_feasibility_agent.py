import os
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import pytest

from app.config import settings
from app.models.workflow import OrderAssessment, CommitmentProposal, DepartmentReadiness, AuditLog
from app.services.feasibility_service import FeasibilityService
from app.agent.feasibility_agent import (
    tool_check_erp,
    tool_check_plm,
    tool_check_mms,
    tool_check_mes,
    tool_check_wms,
    tool_check_qms,
    tool_check_tms,
    tool_check_atp,
    tool_check_ctp,
    tool_recommend_promise_date,
    tool_propose_allocation,
    tool_get_competing_orders,
    run_feasibility_agent,
    FeasibilityAgentDecision,
)


def test_feasibility_tools_direct(db_session):
    """Verify all 12 feasibility and commitment tools execute directly and return valid schemas."""
    ref_d = "2026-08-01"
    req_d = "2026-08-25"

    # 1. check_erp
    erp = tool_check_erp(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=100,
        requested_delivery_date=req_d,
        as_of_date=ref_d,
    )
    assert erp["department"] == "ERP"
    assert "readiness_status" in erp

    # 2. check_plm
    plm = tool_check_plm(
        db=db_session,
        product_id="SPH-A15-128",
        as_of_date=ref_d,
    )
    assert plm["department"] == "PLM"
    assert plm["readiness_status"] == "READY"

    # 3. check_mms
    mms = tool_check_mms(
        db=db_session,
        product_id="SPH-A15-128",
        order_qty=100,
        as_of_date=ref_d,
    )
    assert mms["department"] == "MMS"
    assert "readiness_status" in mms

    # 4. check_mes
    mes = tool_check_mes(
        db=db_session,
        product_id="SPH-A15-128",
        order_qty=100,
        requested_delivery_date=req_d,
        as_of_date=ref_d,
    )
    assert mes["department"] == "MES"
    assert "readiness_status" in mes

    # 5. check_wms
    wms = tool_check_wms(
        db=db_session,
        product_id="SPH-A15-128",
        order_qty=100,
        requested_delivery_date=req_d,
        as_of_date=ref_d,
    )
    assert wms["department"] == "WMS"
    assert "readiness_status" in wms

    # 6. check_qms
    qms = tool_check_qms(
        db=db_session,
        product_id="SPH-A15-128",
    )
    assert qms["department"] == "QMS"
    assert "readiness_status" in qms

    # 7. check_tms
    tms = tool_check_tms(
        db=db_session,
        customer_id="CUS-001",
    )
    assert tms["department"] == "TMS"
    assert "readiness_status" in tms

    # 8. check_atp
    atp = tool_check_atp(
        db=db_session,
        product_id="SPH-A15-128",
        order_qty=100,
    )
    assert "is_atp_feasible" in atp
    assert "max_producible_units" in atp

    # 9. check_ctp
    ctp = tool_check_ctp(
        db=db_session,
        product_id="SPH-A15-128",
        order_qty=100,
    )
    assert "days_to_produce" in ctp
    assert "daily_capacity_units" in ctp

    # 10. recommend_promise_date
    rec = tool_recommend_promise_date(
        db=db_session,
        product_id="SPH-A15-128",
        order_qty=100,
        customer_id="CUS-001",
    )
    assert "recommended_date" in rec

    # 11. propose_allocation
    alloc = tool_propose_allocation(
        db=db_session,
        product_id="SPH-A15-128",
    )
    assert "total_usable_inventory_units" in alloc

    # 12. get_competing_orders
    comp = tool_get_competing_orders(
        db=db_session,
        product_id="SPH-A15-128",
    )
    assert "competing_orders_count" in comp
    assert "active_production_queue_orders" in comp


def test_rules_mode_produces_valid_assessment(db_session, test_user, monkeypatch):
    """Verify that in rules mode, FeasibilityService produces a valid assessment with PENDING proposal."""
    monkeypatch.setenv("FEASIBILITY_AGENT_MODE", "rules")
    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=25)

    assessment = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_qty=100,
        requested_delivery_date=req_date,
        user=test_user,
        unit_price_inr=19000.0,
        submit_for_approval=True,
        as_of_date=ref_date,
    )

    assert assessment.id is not None
    assert assessment.overall_status in ["FEASIBLE", "FEASIBLE_WITH_RISKS"]
    assert assessment.agent_disagreement is False
    assert assessment.agent_reasoning is None
    assert assessment.agent_output is None

    # Proposal must exist and be strictly PENDING
    assert assessment.proposal_id is not None
    proposal = db_session.query(CommitmentProposal).filter(CommitmentProposal.id == assessment.proposal_id).first()
    assert proposal is not None
    assert proposal.status == "PENDING"


def test_agentic_mode_produces_valid_assessment(db_session, test_user, monkeypatch):
    """
    Verify that in agentic mode:
    - Agent 2 executes ReAct loop calling check_erp and check_plm first.
    - Successfully returns a valid FeasibilityAgentDecision conforming to schema.
    - When delivery date is within 2 days of rule calculation, agent values are adopted.
    - Agent reasoning and output are persisted.
    - Proposal remains strictly PENDING.
    """
    monkeypatch.setenv("FEASIBILITY_AGENT_MODE", "agentic")
    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=25)
    agent_date_str = str(ref_date + timedelta(days=25))

    turn_responses = [
        # Turn 1: Call check_erp first
        json.dumps({
            "thought": "Mandatory first step: I must check ERP commercial and credit readiness first.",
            "action": "check_erp",
            "input": {
                "customer_id": "CUS-001",
                "product_id": "SPH-A15-128",
                "order_qty": 100,
                "requested_delivery_date": str(req_date),
            },
        }),
        # Turn 2: Call check_plm next
        json.dumps({
            "thought": "Mandatory first step: ERP is READY. Now checking PLM engineering readiness.",
            "action": "check_plm",
            "input": {"product_id": "SPH-A15-128"},
        }),
        # Turn 3: Final feasibility decision
        json.dumps({
            "thought": "All initial checks pass. Finalizing achievable delivery date.",
            "action": "final",
            "confidence": "HIGH",
            "overall_status": "FEASIBLE",
            "estimated_delivery_date": agent_date_str,
            "per_department_days": {
                "ERP": 0,
                "MMS": 2,
                "MES": 9,
                "WMS": 1,
                "QMS": 0,
                "TMS": 3,
                "PLM": 0,
            },
            "blockers": [],
            "corrective_actions": ["Reserve plant line for 9 days"],
            "proposal_reasons": ["Component stock available; 9 days assembly throughput confirmed"],
            "answer": "Order is fully feasible for production and shipment.",
        }),
    ]

    mock_invoke = MagicMock(side_effect=turn_responses)

    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.feasibility_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        assessment = FeasibilityService.assess_new_order(
            db=db_session,
            customer_id="CUS-001",
            product_id="SPH-A15-128",
            order_qty=100,
            requested_delivery_date=req_date,
            user=test_user,
            unit_price_inr=19000.0,
            submit_for_approval=True,
            as_of_date=ref_date,
        )

        assert assessment.id is not None
        assert assessment.agent_disagreement is False
        assert assessment.agent_reasoning is not None
        assert len(assessment.agent_reasoning) >= 2
        assert assessment.agent_output is not None
        assert assessment.agent_output.get("overall_status") == "FEASIBLE"
        assert assessment.estimated_delivery_date == date.fromisoformat(agent_date_str)

        # Proposal must still be strictly PENDING
        assert assessment.proposal_id is not None
        proposal = db_session.query(CommitmentProposal).filter(CommitmentProposal.id == assessment.proposal_id).first()
        assert proposal.status == "PENDING"
        assert proposal.proposed_date == date.fromisoformat(agent_date_str)


def test_agent_disagreement_fallback_on_date_variance(db_session, test_user, monkeypatch):
    """
    Test that if the agent's estimated delivery date differs from the rule-based
    critical-path date by more than 2 days:
    - agent_disagreement is set to True.
    - 'agent_disagreement' is added to missing_data.
    - Rule engine status, date, blockers, and actions are retained.
    """
    monkeypatch.setenv("FEASIBILITY_AGENT_MODE", "agentic")
    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=25)
    # Give agent a date 60 days in the future (large variance > 2 days)
    deviant_agent_date = str(ref_date + timedelta(days=60))

    turn_responses = [
        json.dumps({
            "thought": "Checking ERP first.",
            "action": "check_erp",
            "input": {"customer_id": "CUS-001", "product_id": "SPH-A15-128", "order_qty": 100, "requested_delivery_date": str(req_date)},
        }),
        json.dumps({
            "thought": "Checking PLM next.",
            "action": "check_plm",
            "input": {"product_id": "SPH-A15-128"},
        }),
        json.dumps({
            "thought": "Deviant date far in the future.",
            "action": "final",
            "confidence": "LOW",
            "overall_status": "FEASIBLE",
            "estimated_delivery_date": deviant_agent_date,
            "per_department_days": {"ERP": 0, "PLM": 0},
            "blockers": ["Unsubstantiated 60-day lead time"],
            "corrective_actions": [],
            "proposal_reasons": ["Arbitrary buffer applied"],
            "answer": "Order delayed by 60 days.",
        }),
    ]

    mock_invoke = MagicMock(side_effect=turn_responses)

    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.feasibility_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        assessment = FeasibilityService.assess_new_order(
            db=db_session,
            customer_id="CUS-001",
            product_id="SPH-A15-128",
            order_qty=100,
            requested_delivery_date=req_date,
            user=test_user,
            unit_price_inr=19000.0,
            submit_for_approval=True,
            as_of_date=ref_date,
        )

        assert assessment.agent_disagreement is True
        assert "agent_disagreement" in assessment.missing_data
        # As per Phase 2: Agent result is retained as source of truth, not overwritten
        assert assessment.estimated_delivery_date == date.fromisoformat(deviant_agent_date)
        assert assessment.result_source == "AGENT"
        assert assessment.confidence_level in ["LOW", "MEDIUM"]
        assert "rule_baseline" in assessment.agent_output
        # Agent reasoning and output should still be preserved for auditing
        assert assessment.agent_reasoning is not None
        assert assessment.agent_output is not None
        assert assessment.proposal is not None
        assert assessment.proposal.status == "PENDING"
        assert assessment.proposal.proposed_date == assessment.estimated_delivery_date


def test_agent_disagreement_fallback_on_blocked_rule(db_session, test_user, monkeypatch):
    """
    Test that if any department is BLOCKED or INSUFFICIENT_DATA in the rule engine
    (e.g., non-existent customer CUS-999), even if the agent claims FEASIBLE:
    - agent_disagreement is set to True.
    - Rule engine result NOT_FEASIBLE / BLOCKED is enforced.
    - 'agent_disagreement' is added to missing_data.
    """
    monkeypatch.setenv("FEASIBILITY_AGENT_MODE", "agentic")
    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=25)

    turn_responses = [
        json.dumps({
            "thought": "Checking ERP first.",
            "action": "check_erp",
            "input": {"customer_id": "CUS-999", "product_id": "SPH-A15-128", "order_qty": 100, "requested_delivery_date": str(req_date)},
        }),
        json.dumps({
            "thought": "Checking PLM.",
            "action": "check_plm",
            "input": {"product_id": "SPH-A15-128"},
        }),
        json.dumps({
            "thought": "Agent incorrectly hallucinates that invalid customer is feasible.",
            "action": "final",
            "confidence": "HIGH",
            "overall_status": "FEASIBLE",
            "estimated_delivery_date": str(req_date),
            "per_department_days": {"ERP": 0, "PLM": 0},
            "blockers": [],
            "corrective_actions": [],
            "proposal_reasons": ["Assumed customer is verified"],
            "answer": "Approved.",
        }),
    ]

    mock_invoke = MagicMock(side_effect=turn_responses)

    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.feasibility_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        assessment = FeasibilityService.assess_new_order(
            db=db_session,
            customer_id="CUS-999",
            product_id="SPH-A15-128",
            order_qty=100,
            requested_delivery_date=req_date,
            user=test_user,
            unit_price_inr=19000.0,
            submit_for_approval=True,
            as_of_date=ref_date,
        )

        assert assessment.agent_disagreement is True
        assert assessment.overall_status == "NOT_FEASIBLE"
        assert "agent_disagreement" in assessment.missing_data
        assert any("CUS-999" in b or "not found" in b.lower() for b in assessment.blockers_summary)
        assert assessment.proposal is None


def test_blocked_customer_or_product_returns_not_feasible(db_session, test_user):
    """
    Verify in rules mode that unknown customer or inactive product
    always returns overall_status NOT_FEASIBLE with corresponding blocker.
    """
    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=25)

    # 1. Invalid customer
    asm_cust = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-NONEXISTENT",
        product_id="SPH-A15-128",
        order_qty=50,
        requested_delivery_date=req_date,
        user=test_user,
        unit_price_inr=14500.0,
        submit_for_approval=True,
        as_of_date=ref_date,
    )
    assert asm_cust.overall_status == "NOT_FEASIBLE"
    erp_rec = next((r for r in asm_cust.readiness_records if r.department == "ERP"), None)
    assert erp_rec is not None
    assert erp_rec.readiness_status == "BLOCKED"

    # 2. Invalid product
    asm_prod = FeasibilityService.assess_new_order(
        db=db_session,
        customer_id="CUS-001",
        product_id="PRD-NONEXISTENT",
        order_qty=50,
        requested_delivery_date=req_date,
        user=test_user,
        unit_price_inr=14500.0,
        submit_for_approval=True,
        as_of_date=ref_date,
    )
    assert asm_prod.overall_status == "NOT_FEASIBLE"
    plm_rec = next((r for r in asm_prod.readiness_records if r.department == "PLM"), None)
    assert plm_rec is not None
    assert plm_rec.readiness_status == "BLOCKED"


def test_order_context_passed_to_promise_tools(db_session, monkeypatch):
    """
    Unit test: Assert that for a non-CUS-001 customer with a non-default price, priority and date,
    the temporary FactCustomerOrder built from order_context and passed to
    svc_check_atp, svc_check_ctp, and svc_recommend_promise_date carries those exact values.
    """
    ref_d = date(2026, 8, 1)
    req_d = date(2026, 9, 15)
    custom_customer = "CUS-002"
    custom_product = "SPH-A15-256"
    custom_qty = 320
    custom_price = 28500.0
    custom_priority = "HIGH"
    custom_channel = "PORTAL"

    captured_orders = {}

    import app.agent.feasibility_agent as fa
    orig_atp = fa.svc_check_atp
    orig_ctp = fa.svc_check_ctp
    orig_rec = fa.svc_recommend_promise_date

    def mock_atp(db, customer_order_id, order=None):
        captured_orders["atp"] = order
        return orig_atp(db, customer_order_id, order=order)

    def mock_ctp(db, customer_order_id, order=None):
        captured_orders["ctp"] = order
        return orig_ctp(db, customer_order_id, order=order)

    def mock_rec(db, customer_order_id, order=None):
        captured_orders["rec"] = order
        return orig_rec(db, customer_order_id, order=order)

    monkeypatch.setattr(fa, "svc_check_atp", mock_atp)
    monkeypatch.setattr(fa, "svc_check_ctp", mock_ctp)
    monkeypatch.setattr(fa, "svc_recommend_promise_date", mock_rec)

    ctx = {
        "customer_id": custom_customer,
        "product_id": custom_product,
        "order_qty": custom_qty,
        "requested_delivery_date": req_d,
        "unit_price_inr": custom_price,
        "priority": custom_priority,
        "channel": custom_channel,
        "as_of_date": ref_d,
        "customer_order_id": "ORD-TEST-CTX-001",
    }

    tool_check_atp(db=db_session, order_context=ctx)
    tool_check_ctp(db=db_session, order_context=ctx)
    tool_recommend_promise_date(db=db_session, order_context=ctx)

    for tool_name in ["atp", "ctp", "rec"]:
        ord_obj = captured_orders[tool_name]
        assert ord_obj is not None
        assert ord_obj.customer_id == custom_customer
        assert ord_obj.product_id == custom_product
        assert ord_obj.order_qty == custom_qty
        assert ord_obj.unit_price_inr == custom_price
        assert ord_obj.priority == custom_priority
        assert ord_obj.channel == custom_channel
        assert ord_obj.requested_delivery_date == req_d
        assert ord_obj.order_date == ref_d


def test_early_stop_when_erp_blocked(db_session, test_user, monkeypatch):
    """
    Unit test: Assert that when ERP is BLOCKED in an agentic run, the agent stops early,
    departments_evaluated contains only the evaluated departments,
    stopped_early is True, and un-evaluated departments are marked NOT_EVALUATED.
    """
    monkeypatch.setenv("FEASIBILITY_AGENT_MODE", "agentic")
    ref_date = date(2026, 8, 1)
    req_date = ref_date + timedelta(days=25)

    turn_responses = [
        json.dumps({
            "thought": "Checking ERP first.",
            "action": "check_erp",
            "input": {
                "customer_id": "CUS-001",
                "product_id": "SPH-A15-128",
                "order_qty": 100,
                "requested_delivery_date": str(req_date),
            },
        }),
        json.dumps({
            "thought": "ERP returned BLOCKED due to customer on credit stop. Terminating evaluation early.",
            "action": "final",
            "confidence": "HIGH",
            "overall_status": "NOT_FEASIBLE",
            "estimated_delivery_date": str(req_date),
            "per_department_days": {"ERP": 0},
            "blockers": ["Customer credit check BLOCKED"],
            "corrective_actions": ["Resolve credit hold with finance"],
            "proposal_reasons": ["ERP blocked due to commercial credit hold"],
            "answer": "Assessment terminated early: ERP is BLOCKED.",
        }),
    ]

    mock_invoke = MagicMock(side_effect=turn_responses)

    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.feasibility_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        assessment = FeasibilityService.assess_new_order(
            db=db_session,
            customer_id="CUS-001",
            product_id="SPH-A15-128",
            order_qty=100,
            requested_delivery_date=req_date,
            user=test_user,
            unit_price_inr=19000.0,
            submit_for_approval=False,
            as_of_date=ref_date,
        )

        assert assessment.stopped_early is True
        assert "ERP" in assessment.departments_evaluated
        assert len(assessment.departments_evaluated) < 7
        not_eval = [r for r in assessment.readiness_records if r.readiness_status == "NOT_EVALUATED"]
        assert len(not_eval) > 0

