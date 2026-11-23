import pytest
from app.agent.agent_loop import run_agent_loop, route_supported_intent
from app.services.promise_service import check_atp, check_ctp, propose_allocation
from app.services.kpi_service import KPIService


def test_regression_1_order_status_routing(db_session):
    """1. Order status question must use get_order_status."""
    tool, args, clarification = route_supported_intent(
        db_session,
        "What is the status of customer order CO-000001?",
        history=[]
    )
    assert tool == "get_order_status"
    assert args["customer_order_id"] == "CO-000001"
    assert clarification is None

    ans, steps = run_agent_loop(
        db_session,
        "What is the status of customer order CO-000001?",
        history=[]
    )
    assert len(steps) >= 1
    assert steps[0]["tool"] == "get_order_status"
    assert "CO-000001" in ans
    assert "Source tables used" in ans


def test_regression_2_at_risk_orders_routing(db_session):
    """2. At-risk questions must use list_at_risk_orders."""
    tool, args, clarification = route_supported_intent(
        db_session,
        "Show me all delayed orders at risk",
        history=[]
    )
    assert tool == "list_at_risk_orders"
    assert clarification is None

    ans, steps = run_agent_loop(
        db_session,
        "Show me delayed orders currently at risk",
        history=[]
    )
    assert len(steps) >= 1
    assert steps[0]["tool"] == "list_at_risk_orders"
    assert "At-Risk Orders" in ans or "at-risk" in ans.lower() or "at risk" in ans.lower()


def test_regression_3_customer_summary_routing_with_name_resolution(db_session):
    """3. Customer-summary questions must resolve customer name and use get_customer_summary."""
    tool, args, clarification = route_supported_intent(
        db_session,
        "Summarize Digital Bazaar's orders and account performance",
        history=[]
    )
    assert tool == "get_customer_summary"
    assert args["customer_id"] == "CUS-003"
    assert clarification is None

    ans, steps = run_agent_loop(
        db_session,
        "Summarize Digital Bazaar's orders",
        history=[]
    )
    assert len(steps) >= 1
    assert steps[0]["tool"] == "get_customer_summary"
    assert steps[0]["input"]["customer_id"] == "CUS-003"
    assert "Digital Bazaar" in ans


def test_regression_4_shipment_status_routing(db_session):
    """4. Shipment status questions must use get_order_delay_analysis."""
    tool, args, clarification = route_supported_intent(
        db_session,
        "Where is the shipment for order CO-000005? Has carrier tracking updated?",
        history=[]
    )
    assert tool == "get_order_delay_analysis"
    assert args["customer_order_id"] == "CO-000005"
    assert clarification is None

    ans, steps = run_agent_loop(
        db_session,
        "Where is the shipment for order CO-000005?",
        history=[]
    )
    assert len(steps) >= 1
    assert steps[0]["tool"] == "get_order_delay_analysis"
    assert steps[0]["input"]["customer_order_id"] == "CO-000005"


def test_regression_5_quality_inspection_routing(db_session):
    """5. Quality inspection questions must use get_order_delay_analysis."""
    tool, args, clarification = route_supported_intent(
        db_session,
        "What is the quality inspection and release status for order CO-000001?",
        history=[]
    )
    assert tool == "get_order_delay_analysis"
    assert args["customer_order_id"] == "CO-000001"
    assert clarification is None


def test_regression_6_follow_up_referring_to_previous_order(db_session):
    """6. Follow-up referring to previous order reuses the previous order ID."""
    history = [
        {"role": "user", "content": "Check order CO-000001"},
        {"role": "assistant", "content": "Customer order CO-000001 is CONFIRMED."},
    ]
    tool, args, clarification = route_supported_intent(
        db_session,
        "Why was that order delayed?",
        history=history,
    )
    assert tool == "get_order_delay_analysis"
    assert args["customer_order_id"] == "CO-000001"
    assert clarification is None

    ans, steps = run_agent_loop(
        db_session,
        "Why is its delivery delayed?",
        history=history,
    )
    assert len(steps) >= 1
    assert steps[0]["input"]["customer_order_id"] == "CO-000001"


def test_regression_7_new_question_referring_to_different_order(db_session):
    """7. New question referring to a different order MUST NOT reuse the previous order ID."""
    history = [
        {"role": "user", "content": "Check order CO-000001"},
        {"role": "assistant", "content": "Customer order CO-000001 is CONFIRMED."},
    ]
    tool, args, clarification = route_supported_intent(
        db_session,
        "Now check the status of CO-000005",
        history=history,
    )
    assert tool == "get_order_status"
    assert args["customer_order_id"] == "CO-000005"
    assert args["customer_order_id"] != "CO-000001"


def test_regression_8_tool_failure_and_invalid_arguments(db_session):
    """8. Invalid order arguments report explicit errors without fabricating data."""
    ans, steps = run_agent_loop(
        db_session,
        "What is the status of customer order CO-999999?",
        history=[],
    )
    assert len(steps) >= 1
    assert "error" in steps[0]["output"]
    assert "was not found" in steps[0]["output"]["error"]
    assert "CO-999999" in ans


def test_regression_9_missing_identifier_asks_clarification(db_session):
    """9. Missing order identifier without history asks for clarification directly."""
    tool, args, clarification = route_supported_intent(
        db_session,
        "What is the order status?",
        history=[],
    )
    assert tool is None
    assert clarification is not None
    assert "specify the Customer Order ID" in clarification


def test_safeguard_atp_insufficient_data(db_session):
    """ATP must report explicit INSUFFICIENT_DATA and BOM data gap warning."""
    res = check_atp(db_session, "CO-000001")
    assert res.status == "INSUFFICIENT_DATA"
    assert "No verified Bill of Materials (BOM) table exists" in res.data_gap_warning


def test_safeguard_ctp_unlinked_production_data(db_session):
    """CTP must report explicit INSUFFICIENT_DATA and unlinked production warning."""
    res = check_ctp(db_session, "CO-000001")
    assert res.status == "INSUFFICIENT_DATA"
    assert res.data_gap_warning is not None
    assert "No verified direct production order linkage exists" in res.data_gap_warning


def test_safeguard_allocation_unsupported_data(db_session):
    """Allocation proposal must report UNSUPPORTED_DATA for finished goods."""
    res = propose_allocation(db_session, product_id="SPH-A15-128")
    assert res.status == "UNSUPPORTED_DATA"
    assert "raw material IDs" in res.data_gap_warning


def test_safeguard_kpi_expedite_cost_proxy_and_otif_target(db_session):
    """Expedite cost KPI must be labeled as proxy and OTIF target separated."""
    kpis = KPIService.get_kpis(db_session)
    assert kpis.expedite_cost.is_proxy is True
    assert "Proxy" in kpis.expedite_cost.metric_label
    assert kpis.otif.target_otif_pct == 95.0
    assert "Data quality caveat" in kpis.otif.data_quality_caveat
    assert kpis.schedule_adherence.adherence_type == "PRODUCTION_SCHEDULE_ADHERENCE"
