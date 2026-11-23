import pytest


def test_dashboard_summary(client, auth_headers):
    res = client.get("/api/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_orders"] == 1500
    assert data["delivered_orders"] > 0
    assert data["delayed_orders_count"] >= 0
    assert data["data_quality_missing_po_count"] > 0


def test_dashboard_order_status_distribution(client, auth_headers):
    res = client.get("/api/dashboard/order-status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 4
    statuses = {item["status"] for item in data}
    assert "DELIVERED" in statuses
    assert "IN_PRODUCTION" in statuses


def test_dashboard_at_risk_orders(client, auth_headers):
    res = client.get("/api/dashboard/at-risk?page_size=10", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_at_risk" in data
    assert "actual_delayed" in data
    assert "potential_delayed" in data
    assert "items" in data
    if data["items"]:
        assert data["items"][0]["risk"]["category"] != "ON_SCHEDULE"

