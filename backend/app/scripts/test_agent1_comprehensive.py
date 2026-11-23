import sys
import uuid
import httpx

sys.path.insert(0, 'backend')
from app.config import settings

def run_agent1_tests():
    print("=" * 80, flush=True)
    print("LIVE VERIFICATION: AGENT 1 (ORDER Q&A ASSISTANT)", flush=True)
    print("=" * 80, flush=True)

    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=60.0)

    # 1. Login as Admin
    print("\n[STEP 1: AUTHENTICATION] Logging in as Admin...", flush=True)
    login_resp = client.post("/api/auth/login", json={"email": settings.admin_email, "password": settings.admin_password})
    assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"  Login successful: {login_resp.json()['user']['full_name']} ({login_resp.json()['user']['role']})", flush=True)

    conv_id = f"test-conv-{uuid.uuid4().hex[:8]}"

    # Test 1.1: Order Status Inquiry (CO-000001)
    print(f"\n[AGENT 1 -> 1.1] Asking order status inquiry for 'CO-000001' (Conversation: {conv_id})...", flush=True)
    chat_payload = {
        "message": "What is the status and delivery date for order CO-000001?",
        "conversation_id": conv_id,
    }
    res_chat = client.post("/api/agent/chat", json=chat_payload, headers=headers)
    print(f"  POST /api/agent/chat -> Status: {res_chat.status_code}", flush=True)
    assert res_chat.status_code == 200, f"Chat failed: {res_chat.text}"
    data = res_chat.json()
    print(f"  Provider: {data.get('provider')}", flush=True)
    print(f"  AI Available: {data.get('ai_available')}", flush=True)
    print(f"  Steps Executed: {len(data.get('steps', []))}", flush=True)
    for s in data.get("steps", []):
        print(f"    - Tool: {s.get('tool')} | Status: {s.get('status')} | Thought: {s.get('thought')}", flush=True)
    print(f"  Answer Snippet:\n{data.get('answer', '')[:300]}...", flush=True)

    # Test 1.2: Follow-up question in the same conversation
    print(f"\n[AGENT 1 -> 1.2] Asking follow-up question: 'Why is it delayed?'...", flush=True)
    res_followup = client.post(
        "/api/agent/chat",
        json={"message": "Why is it delayed?", "conversation_id": conv_id},
        headers=headers
    )
    assert res_followup.status_code == 200, f"Follow-up failed: {res_followup.text}"
    data_fu = res_followup.json()
    print(f"  Follow-up Steps: {len(data_fu.get('steps', []))}", flush=True)
    for s in data_fu.get("steps", []):
        print(f"    - Tool: {s.get('tool')} | Status: {s.get('status')}", flush=True)
    print(f"  Follow-up Answer Snippet:\n{data_fu.get('answer', '')[:300]}...", flush=True)

    # Test 1.3: Customer Summary Inquiry (Dynamic customer)
    print(f"\n[AGENT 1 -> 1.3] Asking customer summary inquiry for 'Digital Bazaar'...", flush=True)
    res_cust = client.post(
        "/api/agent/chat",
        json={"message": "Can you summarize orders for Digital Bazaar?", "conversation_id": conv_id},
        headers=headers
    )
    assert res_cust.status_code == 200, f"Customer query failed: {res_cust.text}"
    data_cust = res_cust.json()
    print(f"  Customer Inquiry Provider: {data_cust.get('provider')}", flush=True)
    print(f"  Customer Inquiry Answer Snippet:\n{data_cust.get('answer', '')[:300]}...", flush=True)

    # Test 1.4: At-risk orders inquiry
    print(f"\n[AGENT 1 -> 1.4] Asking: 'Which orders are currently delayed or at risk?'...", flush=True)
    res_risk = client.post(
        "/api/agent/chat",
        json={"message": "Which orders are currently delayed or at risk?", "conversation_id": conv_id},
        headers=headers
    )
    assert res_risk.status_code == 200, f"At-risk query failed: {res_risk.text}"
    data_risk = res_risk.json()
    print(f"  At-Risk Query Steps: {len(data_risk.get('steps', []))}", flush=True)
    print(f"  At-Risk Answer Snippet:\n{data_risk.get('answer', '')[:300]}...", flush=True)

    # Test 1.5: Conversation History Retrieval
    print(f"\n[AGENT 1 -> 1.5] Verifying Conversation History in DB...", flush=True)
    res_msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=headers)
    assert res_msgs.status_code == 200, f"History query failed: {res_msgs.text}"
    messages = res_msgs.json()
    print(f"  Total Messages Saved in DB for Conversation: {len(messages)}", flush=True)
    for m in messages:
        print(f"    - [{m.get('role').upper()}] {m.get('content')[:60]}... (Steps: {len(m.get('steps') or [])})", flush=True)

    # Test 1.6: Unknown Order Handling
    print(f"\n[AGENT 1 -> 1.6] Edge Case: Querying non-existent order 'CO-999999'...", flush=True)
    res_unk = client.post(
        "/api/agent/chat",
        json={"message": "What is the status of order CO-999999?", "conversation_id": conv_id},
        headers=headers
    )
    assert res_unk.status_code == 200, f"Unknown order query failed: {res_unk.text}"
    data_unk = res_unk.json()
    print(f"  Unknown Order Response: {data_unk.get('answer')[:200]}...", flush=True)

    # Test 1.7: Unauthorized Request (No Token)
    print(f"\n[AGENT 1 -> 1.7] Security Check: Calling chat without token...", flush=True)
    res_unauth = client.post("/api/agent/chat", json={"message": "Hello"})
    print(f"  Unauthenticated status: {res_unauth.status_code} (Expected: 401)", flush=True)
    assert res_unauth.status_code == 401, f"Expected 401, got {res_unauth.status_code}"

    print("\n" + "=" * 80, flush=True)
    print("ALL AGENT 1 TESTS PASSED SUCCESSFULLY!", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    run_agent1_tests()
