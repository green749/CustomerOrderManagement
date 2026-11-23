import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
results = []

def test_endpoint(name, method, path, data=None, headers=None, expected_status=200):
    url = f"{BASE_URL}{path}"
    req_headers = headers or {}
    encoded_data = None
    if data is not None:
        encoded_data = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            cookie_headers = resp.headers.get_all("Set-Cookie") or []
            data_json = None
            try:
                data_json = json.loads(content)
            except:
                pass
            success = (status == expected_status)
            results.append({
                "test": name,
                "method": method,
                "path": path,
                "status": status,
                "success": success,
                "cookies": cookie_headers,
                "data": data_json or content[:100]
            })
            print(f"[{'PASS' if success else 'FAIL'}] {method:4} {path:45} -> HTTP {status}")
            return status, data_json, cookie_headers
    except urllib.error.HTTPError as e:
        status = e.code
        content = e.read().decode("utf-8")
        success = (status == expected_status)
        results.append({
            "test": name,
            "method": method,
            "path": path,
            "status": status,
            "success": success,
            "cookies": [],
            "data": content
        })
        print(f"[{'PASS' if success else 'FAIL'}] {method:4} {path:45} -> HTTP {status}")
        return status, None, []
    except Exception as ex:
        results.append({
            "test": name,
            "method": method,
            "path": path,
            "status": 0,
            "success": False,
            "cookies": [],
            "data": str(ex)
        })
        print(f"[FAIL] {method:4} {path:45} -> EXCEPTION: {ex}")
        return 0, None, []

print("=" * 80)
print("COMPREHENSIVE BACKEND API TEST SUITE (17 ENDPOINTS + ERROR CASES)")
print("Target: Neon PostgreSQL + Live Domo AI Agent")
print("=" * 80)

# 1. System Health
test_endpoint("Root Metadata", "GET", "/")
test_endpoint("Database & Service Health", "GET", "/api/health")

# 2. Authentication Flow
admin_pwd = os.getenv("ADMIN_PASSWORD", "")
_, login_data, cookies = test_endpoint(
    "Auth Login (Valid)", "POST", "/api/auth/login",
    data={"email": "admin@manufacturing.com", "password": admin_pwd}
)
access_token = login_data.get("access_token") if login_data else ""
auth_headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

# Extract refresh token cookie
refresh_cookie_str = ""
for c in cookies:
    if "refresh_token=" in c:
        refresh_cookie_str = c.split(";")[0]

test_endpoint("Auth Login (Invalid Password - 401)", "POST", "/api/auth/login",
    data={"email": "admin@manufacturing.com", "password": "WrongPassword!"},
    expected_status=401
)

test_endpoint("Auth Get Profile (/me)", "GET", "/api/auth/me", headers=auth_headers)

# 3. Dashboard Endpoints
test_endpoint("Dashboard Summary KPIs", "GET", "/api/dashboard/summary", headers=auth_headers)
test_endpoint("Dashboard Status Distribution", "GET", "/api/dashboard/order-status", headers=auth_headers)
test_endpoint("Dashboard At-Risk Orders", "GET", "/api/dashboard/at-risk?page=1&page_size=5", headers=auth_headers)
test_endpoint("Delivery Performance (Customer & Carrier)", "GET", "/api/dashboard/delivery-performance", headers=auth_headers)
test_endpoint("Weekly Order Volume & OTIF Trends", "GET", "/api/dashboard/trends?weeks=8", headers=auth_headers)

# 3b. KPIs Endpoint (Slide Deliverables)
test_endpoint("Comprehensive KPIs (SQL Aggregates)", "GET", "/api/kpis", headers=auth_headers)
test_endpoint("KPIs Filtered by Customer", "GET", "/api/kpis?customer_id=CUS-001", headers=auth_headers)

# 4. Orders Endpoints
_, orders_data, _ = test_endpoint("Orders List (Paginated)", "GET", "/api/orders?page=1&page_size=5", headers=auth_headers)
first_order_id = "CO-000001"
if orders_data and "items" in orders_data and len(orders_data["items"]) > 0:
    first_order_id = orders_data["items"][0]["customer_order_id"]

test_endpoint(f"Order Detail ({first_order_id})", "GET", f"/api/orders/{first_order_id}", headers=auth_headers)
test_endpoint(f"Order Timeline ({first_order_id})", "GET", f"/api/orders/{first_order_id}/timeline", headers=auth_headers)
test_endpoint("Overdue Orders Alert", "GET", "/api/orders/overdue?page=1&page_size=5", headers=auth_headers)
test_endpoint(f"Order Status Draft ({first_order_id})", "GET", f"/api/orders/{first_order_id}/status-draft", headers=auth_headers)
test_endpoint(f"Order Escalation Pack ({first_order_id})", "GET", f"/api/orders/{first_order_id}/escalation-pack", headers=auth_headers)
test_endpoint(f"Order ATP/CTP Analysis ({first_order_id})", "GET", f"/api/orders/{first_order_id}/atp-ctp", headers=auth_headers)
test_endpoint(f"Order Promise Recommendation ({first_order_id})", "GET", f"/api/orders/{first_order_id}/promise-recommendation", headers=auth_headers)

# 4b. Commercial Commitment Workflow & Governance
_, prop_data, _ = test_endpoint(
    f"Create Commitment Proposal ({first_order_id})", "POST", f"/api/orders/{first_order_id}/commitment-proposals",
    data={"recommended_by": "agent", "reasons": ["Automated promise date calculation", "ATP/CTP verified"]},
    headers=auth_headers,
    expected_status=201
)
prop_id = prop_data.get("id") if prop_data else 1

test_endpoint("List Commitment Proposals", "GET", "/api/commitment-proposals", headers=auth_headers)
test_endpoint("List Pending Proposals", "GET", "/api/commitment-proposals?status=PENDING", headers=auth_headers)

if prop_id:
    test_endpoint(f"Approve Commitment Proposal ({prop_id})", "POST", f"/api/commitment-proposals/{prop_id}/approve",
        data={"decision_note": "Commercial terms verified and authorized by Manager"},
        headers=auth_headers
    )
    # Stale/duplicate decision rejection test (400)
    test_endpoint(f"Approve Already-Decided Proposal (400)", "POST", f"/api/commitment-proposals/{prop_id}/approve",
        data={"decision_note": "Duplicate approval attempt"},
        headers=auth_headers,
        expected_status=400
    )

test_endpoint("Stock Allocation Proposal", "GET", "/api/allocation/proposal", headers=auth_headers)
test_endpoint("Stock Allocation Proposal (Filtered)", "GET", "/api/allocation/proposal?product_id=SPH-A15-128", headers=auth_headers)
test_endpoint("Order Detail (404 Non-existent)", "GET", "/api/orders/CO-999999", headers=auth_headers, expected_status=404)

# 5. Inventory Endpoints
_, inv_data, _ = test_endpoint("Raw Materials List", "GET", "/api/inventory/materials?page=1&page_size=5", headers=auth_headers)
first_mat_id = "MAT-SOC-001"
if inv_data and "items" in inv_data and len(inv_data["items"]) > 0:
    first_mat_id = inv_data["items"][0]["material_id"]

test_endpoint(f"Material Summary ({first_mat_id})", "GET", f"/api/inventory/materials/{first_mat_id}/summary", headers=auth_headers)
test_endpoint("Material Summary (404 Non-existent)", "GET", "/api/inventory/materials/MAT-NONEXISTENT/summary", headers=auth_headers, expected_status=404)

# 6. AI Agent Chat & Conversations
_, chat_data, _ = test_endpoint(
    "AI Agent Chat (Live Domo + Neon)", "POST", "/api/agent/chat",
    data={"message": "What is the status of order CO-000001?"},
    headers=auth_headers
)
conv_id = chat_data.get("conversation_id") if chat_data else None

test_endpoint("Conversations List", "GET", "/api/conversations", headers=auth_headers)
if conv_id:
    test_endpoint("Conversation Messages", "GET", f"/api/conversations/{conv_id}/messages", headers=auth_headers)

# 7. Token Refresh & Logout
refresh_headers = {"Cookie": refresh_cookie_str} if refresh_cookie_str else {}
refresh_headers.update(auth_headers)

test_endpoint("Auth Token Refresh", "POST", "/api/auth/refresh", headers=refresh_headers)
test_endpoint("Auth Logout", "POST", "/api/auth/logout", headers=refresh_headers)

# Summary
print("=" * 80)
total_tests = len(results)
passed_tests = sum(1 for r in results if r["success"])
print(f"RESULTS: {passed_tests}/{total_tests} API TESTS PASSED ({passed_tests*100//total_tests}%)")
print("=" * 80)

if passed_tests != total_tests:
    sys.exit(1)

