import pytest
from decimal import Decimal


def test_kpis_endpoint(client, auth_headers):
    """
    Test GET /api/kpis: validates all 6 slide KPIs calculated via SQL aggregates:
    - Customer OTIF
    - Order confirmation time proxy
    - Production schedule adherence
    - Backlog ageing buckets
    - Promise-date accuracy
    - Expedite freight cost
    """
    res = client.get("/api/kpis", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    # 1. OTIF
    assert "otif" in data
    otif = data["otif"]
    assert otif["total_delivered_orders"] > 0
    assert "data_quality_caveat" in otif
    assert otif["otif_rate_pct"] >= 0.0

    # 2. Confirmation Time Proxy
    assert "order_confirmation_time" in data
    conf = data["order_confirmation_time"]
    assert conf["is_proxy"] is True
    assert conf["average_confirmation_days_proxy"] > 0
    assert conf["median_confirmation_days_proxy"] > 0

    # 3. Schedule Adherence
    assert "schedule_adherence" in data
    sched = data["schedule_adherence"]
    assert sched["total_production_orders"] > 0
    assert sched["schedule_adherence_pct"] > 0

    # 4. Backlog Ageing Buckets
    assert "backlog_ageing" in data
    buckets = data["backlog_ageing"]
    assert len(buckets) == 4
    bucket_names = [b["bucket"] for b in buckets]
    assert "0-7 days" in bucket_names
    assert "8-14 days" in bucket_names
    assert "15-30 days" in bucket_names
    assert "30+ days" in bucket_names

    # 5. Promise-Date Accuracy
    assert "promise_date_accuracy" in data
    pda = data["promise_date_accuracy"]
    assert len(pda["confirmed_vs_requested_splits"]) >= 1

    # 6. Expedite Cost
    assert "expedite_cost" in data
    exp = data["expedite_cost"]
    assert Decimal(str(exp["total_expedite_cost_inr"])) >= 0
    assert "definition" in exp


def test_overdue_orders_alert(client, auth_headers):
    """
    Test GET /api/orders/overdue: overdue order alerts deliverable.
    Returns open orders past confirmed delivery date sorted by days overdue.
    """
    res = client.get("/api/orders/overdue?page=1&page_size=10", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    assert len(data["items"]) <= 10

    first_item = data["items"][0]
    assert first_item["order_status"] != "DELIVERED"
    assert first_item["days_overdue"] > 0
    assert "customer_name" in first_item
    assert "priority" in first_item
    assert "release_status" in first_item


def test_order_status_draft(client, auth_headers):
    """
    Test GET /api/orders/{id}/status-draft: templated customer status update.
    """
    order_id = "CO-000001"
    res = client.get(f"/api/orders/{order_id}/status-draft", headers=auth_headers)
    assert res.status_code == 200
    draft = res.json()
    assert draft["customer_order_id"] == order_id
    assert draft["customer_name"] is not None
    assert draft["product_name"] is not None
    assert draft["next_milestone"] is not None
    assert draft["effective_promise_date"] is not None
    assert len(draft["identified_risks"]) > 0
    assert draft["is_polished_by_agent"] is False
    assert "Dear" in draft["draft_body"]


def test_order_escalation_pack(client, auth_headers):
    """
    Test GET /api/orders/{id}/escalation-pack: structured summary for account teams.
    """
    order_id = "CO-000001"
    res = client.get(f"/api/orders/{order_id}/escalation-pack", headers=auth_headers)
    assert res.status_code == 200
    pack = res.json()
    assert pack["customer_order_id"] == order_id
    assert pack["customer_name"] is not None
    assert "risk_level" in pack
    assert "release_status" in pack
    assert "atp_shortages" in pack
    assert "proposed_actions" in pack
    assert len(pack["proposed_actions"]) > 0


def test_delivery_performance_and_weekly_trends(client, auth_headers):
    """
    Test GET /api/dashboard/delivery-performance and GET /api/dashboard/trends:
    Per-customer & per-carrier on-time %, and real weekly order volume/OTIF trends.
    """
    res_perf = client.get("/api/dashboard/delivery-performance", headers=auth_headers)
    assert res_perf.status_code == 200
    perf = res_perf.json()
    assert "customers" in perf
    assert "carriers" in perf
    assert len(perf["customers"]) > 0
    assert len(perf["carriers"]) > 0

    # Carrier performance verification
    carrier0 = perf["carriers"][0]
    assert "carrier" in carrier0
    assert carrier0["total_shipments"] > 0
    assert 0.0 <= carrier0["on_time_pct"] <= 100.0

    # Weekly trends verification
    res_trends = client.get("/api/dashboard/trends?weeks=8", headers=auth_headers)
    assert res_trends.status_code == 200
    trends = res_trends.json()["trends"]
    assert len(trends) == 8
    for t in trends:
        assert "week_label" in t
        assert t["total_orders"] >= 0

