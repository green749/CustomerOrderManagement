import pytest
from app.agent.tools import (
    tool_get_order_status,
    tool_list_at_risk_orders,
    tool_get_customer_summary,
    tool_get_order_delay_analysis,
)


def test_agent_tools_direct_execution(db_session):
    # 1. get_order_status
    st = tool_get_order_status(db_session, "CO-000001")
    assert st["customer_order_id"] == "CO-000001"
    assert "order_status" in st
    assert "risk_level" in st

    # 2. list_at_risk_orders
    risk_list = tool_list_at_risk_orders(db_session, limit=5)
    assert "total_at_risk" in risk_list
    assert len(risk_list["orders"]) <= 5

    # 3. get_customer_summary
    cust = tool_get_customer_summary(db_session, "CUS-001")
    assert cust["customer_id"] == "CUS-001"
    assert cust["total_orders"] > 0

    # 4. get_order_delay_analysis
    analysis = tool_get_order_delay_analysis(db_session, "CO-000001")
    assert analysis["customer_order_id"] == "CO-000001"
    assert "delay_category" in analysis


def test_agent_chat_api(client, auth_headers):
    # Test conversational endpoint with agent
    res = client.post(
        "/api/agent/chat",
        headers=auth_headers,
        json={"message": "What is the status of customer order CO-000001?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert "answer" in data
    assert "steps" in data
    assert isinstance(data["steps"], list)

    conv_id = data["conversation_id"]

    # Verify conversation is persisted
    conv_res = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
    assert conv_res.status_code == 200
    msgs = conv_res.json()
    assert len(msgs) >= 2  # user + assistant
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"

