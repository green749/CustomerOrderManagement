import os
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import pytest

from app.config import settings
from app.models.business import FactCustomerOrder, FactShipmentMilestone
from app.models.workflow import OrderMonitoringRecord, RiskAlert, AuditLog
from app.services.monitoring_service import MonitoringService
from app.agent.monitoring_agent import (
    tool_detect_risks,
    tool_get_related_orders_by_material,
    tool_get_alert_history,
    run_order_monitoring_agent,
    MonitoredRiskItem,
)


def test_monitoring_agent_tools_direct(db_session, test_user):
    """Test direct execution of Agent 3's dedicated investigative tools."""
    order = db_session.query(FactCustomerOrder).first()
    assert order is not None

    # 1. detect_risks
    res_detect = tool_detect_risks(db_session, order.customer_order_id)
    assert res_detect["customer_order_id"] == order.customer_order_id
    assert "risks" in res_detect

    # 2. get_related_orders_by_material
    res_rel = tool_get_related_orders_by_material(db_session, customer_order_id=order.customer_order_id)
    assert "related_orders" in res_rel

    # 3. get_alert_history
    res_hist = tool_get_alert_history(db_session, order.customer_order_id)
    assert res_hist["customer_order_id"] == order.customer_order_id
    assert "alerts" in res_hist


def test_agentic_mode_produces_valid_alerts_and_audit(db_session, monkeypatch):
    """
    Test that in agentic mode:
    - Agent 3 executes investigative tool calls and logs every step to AuditLog with entity='monitoring_agent'.
    - Validates risks via Pydantic MonitoredRiskItem schema.
    - Records alerts via _record_risk_alert with proper dedup fingerprinting.
    - Stays strictly alert-only and does NOT change order data.
    """
    test_order_id = "CO-AGENTIC-001"

    # Clean up prior test runs
    db_session.query(AuditLog).filter(AuditLog.entity == "monitoring_agent").delete()
    db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == test_order_id).delete()
    db_session.query(OrderMonitoringRecord).filter(OrderMonitoringRecord.customer_order_id == test_order_id).delete()
    db_session.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == test_order_id).delete()
    db_session.commit()

    # Create active customer order
    order = FactCustomerOrder(
        customer_order_id=test_order_id,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_date=date(2026, 7, 1),
        requested_delivery_date=date(2026, 7, 20),
        confirmed_delivery_date=date(2026, 7, 20),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=15000.0,
        order_status="IN_PRODUCTION",
        priority="HIGH",
        channel="EDI",
    )
    db_session.add(order)
    db_session.commit()

    turn_responses = [
        # Turn 1: Agent calls detect_risks tool
        json.dumps({
            "thought": "I will inspect baseline risks for this order first.",
            "action": "detect_risks",
            "input": {"customer_order_id": test_order_id},
        }),
        # Turn 2: Agent synthesizes final risks conforming to schema
        json.dumps({
            "thought": "Risk baseline confirmed; delivering synthesized agentic risk alert.",
            "action": "final",
            "confidence": "HIGH",
            "risks": [
                {
                    "department": "ERP",
                    "risk_category": "DELIVERY_DATE_BREACHED",
                    "severity": "CRITICAL",
                    "title": "Agentic: Delivery commitment breached",
                    "description": "Order confirmed date 2026-07-20 is past reference date.",
                    "delivery_impact": "Customer SLA breached by 12 days",
                    "recommended_action": "Notify customer service and expedite fulfillment",
                }
            ],
            "answer": "Agentic monitoring investigation complete.",
        }),
    ]

    mock_invoke = MagicMock(side_effect=turn_responses)

    monkeypatch.setenv("MONITORING_AGENT_MODE", "agentic")
    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.monitoring_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        ref_date = date(2026, 8, 1)

        # Run event check in agentic mode
        alerts = MonitoringService.run_event_check(
            db=db_session,
            customer_order_id=test_order_id,
            as_of_date=ref_date,
        )

        assert len(alerts) >= 1
        agent_alert = next((a for a in alerts if "Agentic:" in a.title), None)
        assert agent_alert is not None
        assert agent_alert.department == "ERP"
        assert agent_alert.severity == "CRITICAL"
        assert agent_alert.risk_category == "DELIVERY_DATE_BREACHED"
        assert agent_alert.delivery_impact == "Customer SLA breached by 12 days"

        # Verify audit logs captured with entity="monitoring_agent"
        audit_records = db_session.query(AuditLog).filter(
            AuditLog.entity == "monitoring_agent"
        ).all()
        assert len(audit_records) >= 1
        tool_call_log = next((l for l in audit_records if l.action == "TOOL_CALL"), None)
        assert tool_call_log is not None
        assert tool_call_log.payload.get("tool") == "detect_risks"
        assert "thought" in tool_call_log.payload
        assert "output" in tool_call_log.payload

        # Verify order remained completely unchanged (ALERT-ONLY)
        db_session.refresh(order)
        assert order.order_status == "IN_PRODUCTION"
        assert order.order_qty == 100
        assert order.product_id == "SPH-A15-128"


def test_invalid_llm_json_falls_back_to_rules(db_session, monkeypatch):
    """
    Test that if Domo LLM returns invalid JSON or fails schema validation,
    the agent seamlessly falls back to rule-based evaluation.
    """
    test_order_id = "CO-FALLBACK-001"

    db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == test_order_id).delete()
    db_session.query(OrderMonitoringRecord).filter(OrderMonitoringRecord.customer_order_id == test_order_id).delete()
    db_session.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == test_order_id).delete()
    db_session.commit()

    order = FactCustomerOrder(
        customer_order_id=test_order_id,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_date=date(2026, 7, 1),
        requested_delivery_date=date(2026, 7, 20),
        confirmed_delivery_date=date(2026, 7, 20),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=15000.0,
        order_status="IN_PRODUCTION",
        priority="HIGH",
        channel="EDI",
    )
    db_session.add(order)
    db_session.commit()

    # Mock LLM returning totally malformed text / invalid JSON
    mock_invoke = MagicMock(return_value="I cannot parse this request properly: { broken json")

    monkeypatch.setenv("MONITORING_AGENT_MODE", "agentic")
    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.monitoring_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        ref_date = date(2026, 8, 1)

        # Run event check: should fall back to rule-based evaluation without crashing
        alerts = MonitoringService.run_event_check(
            db=db_session,
            customer_order_id=test_order_id,
            as_of_date=ref_date,
        )

        # Fallback rules should still have flagged the breached delivery date
        assert len(alerts) >= 1
        breach_alert = next((a for a in alerts if a.risk_category == "DELIVERY_DATE_BREACHED"), None)
        assert breach_alert is not None
        assert "breached approved delivery date" in breach_alert.title


def test_agentic_dedup_holds(db_session, monkeypatch):
    """
    Test that repeating agentic monitoring on the same order with unchanged risks
    deduplicates correctly and does NOT create duplicate RiskAlert rows.
    """
    test_order_id = "CO-DEDUP-001"

    db_session.query(RiskAlert).filter(RiskAlert.customer_order_id == test_order_id).delete()
    db_session.query(OrderMonitoringRecord).filter(OrderMonitoringRecord.customer_order_id == test_order_id).delete()
    db_session.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == test_order_id).delete()
    db_session.commit()

    order = FactCustomerOrder(
        customer_order_id=test_order_id,
        customer_id="CUS-001",
        product_id="SPH-A15-128",
        order_date=date(2026, 7, 1),
        requested_delivery_date=date(2026, 7, 20),
        confirmed_delivery_date=date(2026, 7, 20),
        order_qty=100,
        shipped_qty=0,
        unit_price_inr=15000.0,
        order_status="IN_PRODUCTION",
        priority="HIGH",
        channel="EDI",
    )
    db_session.add(order)
    db_session.commit()

    turn_responses = [
        # Turn 1: Agent calls detect_risks tool
        json.dumps({
            "thought": "I will inspect baseline risks for this order first.",
            "action": "detect_risks",
            "input": {"customer_order_id": test_order_id},
        }),
        # Turn 2: Agent synthesizes final risks conforming to schema
        json.dumps({
            "thought": "Direct final risk assessment.",
            "action": "final",
            "confidence": "HIGH",
            "risks": [
                {
                    "department": "ERP",
                    "risk_category": "DELIVERY_DATE_BREACHED",
                    "severity": "CRITICAL",
                    "title": "Agentic: Confirmed delivery date breached",
                    "description": "Passed commitment date.",
                    "delivery_impact": "Delayed delivery",
                    "recommended_action": "Expedite shipment",
                }
            ],
            "answer": "Risk detected.",
        }),
    ]

    mock_invoke = MagicMock(side_effect=turn_responses * 2)

    monkeypatch.setenv("MONITORING_AGENT_MODE", "agentic")
    monkeypatch.setenv("FEASIBILITY_AGENT_MODE", "rules")
    with patch("app.agent.agent_loop.is_domo_configured", return_value=True), \
         patch("app.agent.domo_client.is_domo_configured", return_value=True), \
         patch("app.services.monitoring_service.is_domo_configured", return_value=True), \
         patch("app.agent.agent_loop.DomoTextLLM.invoke", mock_invoke):

        ref_date = date(2026, 8, 1)

        # Run 1
        alerts_1 = MonitoringService.run_event_check(
            db=db_session,
            customer_order_id=test_order_id,
            as_of_date=ref_date,
        )
        assert len(alerts_1) == 1

        # Run 2
        alerts_2 = MonitoringService.run_event_check(
            db=db_session,
            customer_order_id=test_order_id,
            as_of_date=ref_date,
        )
        assert len(alerts_2) == 1

        # Confirm exactly 1 row exists in RiskAlert table
        total_in_db = db_session.query(RiskAlert).filter(
            RiskAlert.customer_order_id == test_order_id
        ).count()
        assert total_in_db == 1
