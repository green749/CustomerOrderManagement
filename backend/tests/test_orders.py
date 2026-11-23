import pytest


def test_list_orders(client, auth_headers):
    res = client.get("/api/orders?page=1&page_size=10", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1500
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert "risk" in data["items"][0]


def test_list_orders_filtering(client, auth_headers):
    # Filter by status
    res = client.get("/api/orders?status=DELIVERED&page_size=5", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    for item in data["items"]:
        assert item["order_status"] == "DELIVERED"

    # Filter by priority
    res2 = client.get("/api/orders?priority=HIGH&page_size=5", headers=auth_headers)
    assert res2.status_code == 200
    for item in res2.json()["items"]:
        assert item["priority"] == "HIGH"


def test_get_order_detail(client, auth_headers):
    res = client.get("/api/orders/CO-000001", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["customer_order_id"] == "CO-000001"
    assert data["customer"] is not None
    assert data["product"] is not None
    assert "risk" in data
    assert "data_quality_warnings" in data


def test_get_order_detail_not_found(client, auth_headers):
    res = client.get("/api/orders/CO-999999", headers=auth_headers)
    assert res.status_code == 404


def test_get_order_timeline(client, auth_headers):
    res = client.get("/api/orders/CO-000001/timeline", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["customer_order_id"] == "CO-000001"
    assert len(data["events"]) >= 2
    # Verify events are in chronological order
    timestamps = [e["timestamp"] for e in data["events"]]
    assert timestamps == sorted(timestamps)


def test_order_validation_endpoint(client, auth_headers):
    res = client.get("/api/orders/CO-000001/validation", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "overall_status" in data
    assert "checks" in data
    assert "quantities" in data["checks"]
    assert "dates" in data["checks"]
    assert "ship_to" in data["checks"]
    assert "packaging" in data["checks"]
    assert "price" in data["checks"]
    assert "configuration" in data["checks"]


def test_order_detail_includes_validation(client, auth_headers):
    res = client.get("/api/orders/CO-000001", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "validation" in data
    assert data["validation"] is not None
    assert data["validation"]["overall_status"] in ["VALID", "CONFLICT"]


