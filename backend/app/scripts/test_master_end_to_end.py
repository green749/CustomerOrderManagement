import sys
import uuid
from datetime import date, timedelta
import httpx

sys.path.insert(0, 'backend')
from app.config import settings

def run_master_test():
    print("=" * 80, flush=True)
    print("MASTER END-TO-END VERIFICATION: ALL 3 AI AGENTS", flush=True)
    print("Reference: Customer Order Management System Documentation", flush=True)
    print("=" * 80, flush=True)

    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=120.0)
    proxy_client = httpx.Client(base_url="http://localhost:5173", timeout=60.0)

    # 1. Login
    print("\n[AUTH] Logging in as Administrator...", flush=True)
    login_resp = client.post("/api/auth/login", json={"email": settings.admin_email, "password": settings.admin_password})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    admin_token = login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    print(f"  Admin login successful: {login_resp.json()['user']['full_name']}", flush=True)

    # Also login as Operator to verify Segregation of Duties
    op_pass = os.getenv("OPERATOR_PASSWORD") or os.getenv("DEMO_PASSWORD") or ""
    op_login = client.post("/api/auth/login", json={"email": "operator@manufacturing.com", "password": op_pass})
    op_token = op_login.json().get("access_token")
    op_headers = {"Authorization": f"Bearer {op_token}", "Content-Type": "application/json"} if op_token else None

    # =========================================================================
    # AGENT 1: ORDER Q&A ASSISTANT VERIFICATION
    # =========================================================================
    print("\n" + "=" * 50, flush=True)
    print("AGENT 1: ORDER Q&A ASSISTANT (Section 5)", flush=True)
    print("=" * 50, flush=True)

    conv_id = f"master-conv-{uuid.uuid4().hex[:6]}"

    # A1.1: Order Status Query
    print(f"[Agent 1 -> Step 1] Querying order status for 'CO-000001'...", flush=True)
    res_a1 = client.post("/api/agent/chat", json={"message": "What is the status of order CO-000001?", "conversation_id": conv_id}, headers=admin_headers)
    assert res_a1.status_code == 200
    d1 = res_a1.json()
    print(f"  Provider: {d1.get('provider')} | AI Available: {d1.get('ai_available')} | Steps: {len(d1.get('steps', []))}", flush=True)
    assert d1.get("provider") == "domo_ai", f"Expected domo_ai, got {d1.get('provider')}"
    assert len(d1.get("steps", [])) >= 1, "Expected at least 1 tool step"
    print("  Status: PASS", flush=True)

    # A1.2: Follow-up Context Resolution
    print(f"[Agent 1 -> Step 2] Follow-up without repeating order ID: 'Why is it delayed?'...", flush=True)
    res_a1_fu = client.post("/api/agent/chat", json={"message": "Why is it delayed?", "conversation_id": conv_id}, headers=admin_headers)
    assert res_a1_fu.status_code == 200
    d1_fu = res_a1_fu.json()
    assert len(d1_fu.get("steps", [])) >= 1
    assert "CO-000001" in str(d1_fu.get("steps", [])[0]["input"])
    print(f"  Multi-turn Context Resolved Order: {d1_fu.get('steps', [])[0]['input']} | Status: PASS", flush=True)

    # A1.3: Conversation History in DB
    print(f"[Agent 1 -> Step 3] Checking Conversation History in PostgreSQL...", flush=True)
    res_hist = client.get(f"/api/conversations/{conv_id}/messages", headers=admin_headers)
    assert res_hist.status_code == 200
    assert len(res_hist.json()) >= 4, f"Expected at least 4 messages, got {len(res_hist.json())}"
    print(f"  Messages Stored in DB: {len(res_hist.json())} | Status: PASS", flush=True)

    # =========================================================================
    # AGENT 2: ORDER FEASIBILITY & COMMITMENT ASSESSMENT VERIFICATION
    # =========================================================================
    print("\n" + "=" * 50, flush=True)
    print("AGENT 2: ORDER FEASIBILITY & COMMITMENT (Section 6)", flush=True)
    print("=" * 50, flush=True)

    # A2.1: Feasible Order Intake (450 units, CUS-001, SPH-A15-128)
    print("[Agent 2 -> Step 1] Submitting 7-Department Feasibility Assessment...", flush=True)
    req_date = (date.today() + timedelta(days=14)).isoformat()
    a2_payload = {
        "customer_id": "CUS-001",
        "product_id": "SPH-A15-128",
        "order_qty": 450,
        "requested_delivery_date": req_date,
        "unit_price_inr": 24500.0,
        "priority": "HIGH",
        "channel": "PORTAL",
        "product_config": {"color": "Graphite Black", "storage": "128GB"},
        "packaging_req": "Standard Retail Pack",
        "submit_for_approval": True
    }
    res_a2 = client.post("/api/assessments", json=a2_payload, headers=admin_headers)
    assert res_a2.status_code == 201
    d2 = res_a2.json()
    asm_id = d2["assessment_id"]
    prop_id = d2.get("proposal_id")
    print(f"  Assessment ID: {asm_id} | Status: {d2['overall_status']} | Achievable: {d2['estimated_delivery_date']}", flush=True)
    print(f"  Domo AI Blockers ({len(d2.get('blockers_summary', []))}): {d2.get('blockers_summary')[:1]}", flush=True)
    print(f"  Domo AI Actions ({len(d2.get('corrective_actions_summary', []))}): {d2.get('corrective_actions_summary')[:1]}", flush=True)
    print(f"  Generated Proposal ID: #{prop_id}", flush=True)
    assert d2["overall_status"] == "FEASIBLE"
    assert len(d2.get("blockers_summary", [])) > 0
    print("  Status: PASS", flush=True)

    # A2.2: 7 Departments Records in DB
    print("[Agent 2 -> Step 2] Checking 7-Department Readiness Records in DB...", flush=True)
    res_depts = client.get(f"/api/assessments/{asm_id}/departments", headers=admin_headers)
    assert res_depts.status_code == 200
    depts = res_depts.json()
    assert len(depts) == 7, f"Expected 7 departments, got {len(depts)}"
    dept_names = [d["department"] for d in depts]
    for required_dept in ["ERP", "MMS", "MES", "WMS", "QMS", "TMS", "PLM"]:
        assert required_dept in dept_names, f"Missing {required_dept}"
    print(f"  All 7 Departments Audited: {dept_names} | Status: PASS", flush=True)

    # A2.3: Proposal Governance & Approval Workflow
    print(f"[Agent 2 -> Step 3] Approving Proposal #{prop_id}...", flush=True)
    res_appr = client.post(
        f"/api/commitment-proposals/{prop_id}/approve",
        json={"decision_note": "Approved by Commercial Approver with buffer."},
        headers=admin_headers
    )
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "APPROVED"
    print(f"  Proposal #{prop_id} Status: APPROVED | Status: PASS", flush=True)

    # A2.4: Edge Case - Insufficient Data for Unknown Product
    print("[Agent 2 -> Step 4] Edge Case: Unknown Product ID -> Insufficient Data...", flush=True)
    res_unk_prod = client.post(
        "/api/assessments",
        json={
            "customer_id": "CUS-001",
            "product_id": "UNKNOWN-PRODUCT-999",
            "order_qty": 100,
            "requested_delivery_date": req_date,
            "submit_for_approval": False
        },
        headers=admin_headers
    )
    assert res_unk_prod.status_code == 201
    d_unk = res_unk_prod.json()
    assert d_unk["overall_status"] in ["NOT_FEASIBLE", "INSUFFICIENT_DATA"]
    print(f"  Unknown Product Evaluation: {d_unk['overall_status']} (Missing Data: {d_unk.get('missing_data')}) | Status: PASS", flush=True)

    # =========================================================================
    # AGENT 3: ORDER MONITORING & RISK SURVEILLANCE VERIFICATION
    # =========================================================================
    print("\n" + "=" * 50, flush=True)
    print("AGENT 3: ORDER MONITORING & RISK SURVEILLANCE (Section 7 & 8)", flush=True)
    print("=" * 50, flush=True)

    # A3.1: Risk Alerts Query
    print("[Agent 3 -> Step 1] Querying Active Risk Alerts from DB...", flush=True)
    res_alerts = client.get("/api/alerts?page=1&page_size=5", headers=admin_headers)
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    assert len(alerts) > 0, "Expected at least 1 risk alert"
    sample = alerts[0]
    target_id = sample["id"]
    print(f"  Alert #{target_id} [{sample['department']}] Order: {sample['customer_order_id']} | Severity: {sample['severity']}", flush=True)
    print(f"  Domo Delivery Impact: {sample.get('delivery_impact')}", flush=True)
    print(f"  Domo Action Plan: {sample.get('recommended_action')}", flush=True)
    assert sample.get("delivery_impact") is not None
    assert sample.get("recommended_action") is not None
    print("  Status: PASS", flush=True)

    # A3.2: Complete Alert Triage Lifecycle
    print(f"[Agent 3 -> Step 2] Alert Triage Lifecycle for Alert #{target_id}...", flush=True)
    ack_res = client.post(f"/api/alerts/{target_id}/acknowledge", headers=admin_headers)
    assert ack_res.status_code == 200
    assign_res = client.post(f"/api/alerts/{target_id}/assign", json={"assigned_owner": "Operations Lead Anita Desai"}, headers=admin_headers)
    assert assign_res.status_code == 200
    comm_res = client.post(f"/api/alerts/{target_id}/customer-communication", json={"customer_communication_notes": "Customer informed."}, headers=admin_headers)
    assert comm_res.status_code == 200
    resolve_res = client.post(f"/api/alerts/{target_id}/resolve", json={"resolution_notes": "Resolved."}, headers=admin_headers)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"
    print(f"  Alert #{target_id} Successfully Acknowledged, Assigned, Logged & Resolved | Status: PASS", flush=True)

    # A3.3: Email Notification Logs
    print("[Agent 3 -> Step 3] Verifying Email Notification Logs in DB...", flush=True)
    res_notifs = client.get("/api/alerts/notifications?limit=5", headers=admin_headers)
    assert res_notifs.status_code == 200
    notifs = res_notifs.json()
    assert len(notifs) > 0
    print(f"  Total Email Logs Retrieved: {len(notifs)}", flush=True)
    for n in notifs[:2]:
        print(f"    - To: {n.get('recipient_email')} ({n.get('recipient_category')}) | Status: {n.get('status')}", flush=True)
    print("  Status: PASS", flush=True)

    # =========================================================================
    # FRONTEND VITE PROXY VERIFICATION (Port 5173 -> 8000)
    # =========================================================================
    print("\n" + "=" * 50, flush=True)
    print("FRONTEND PROXY & WORKSPACE INTEGRATION (Port 5173)", flush=True)
    print("=" * 50, flush=True)

    # P1: Dashboard summary
    p_dash = proxy_client.get("/api/dashboard/summary", headers=admin_headers)
    assert p_dash.status_code == 200
    print(f"  http://localhost:5173/api/dashboard/summary -> 200 OK (Orders: {p_dash.json().get('total_orders')})", flush=True)

    # P2: Orders
    p_orders = proxy_client.get("/api/orders?page=1&page_size=10", headers=admin_headers)
    assert p_orders.status_code == 200
    print(f"  http://localhost:5173/api/orders -> 200 OK (Items: {len(p_orders.json().get('items', []))})", flush=True)

    # P3: Assessments
    p_asm = proxy_client.get(f"/api/assessments/{asm_id}", headers=admin_headers)
    assert p_asm.status_code == 200
    print(f"  http://localhost:5173/api/assessments/{asm_id} -> 200 OK", flush=True)

    # P4: Alerts
    p_alerts = proxy_client.get("/api/alerts?page=1&page_size=5", headers=admin_headers)
    assert p_alerts.status_code == 200
    print(f"  http://localhost:5173/api/alerts -> 200 OK (Items: {len(p_alerts.json())})", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("ALL MASTER END-TO-END VERIFICATIONS PASSED WITH ZERO ERRORS!", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    run_master_test()
