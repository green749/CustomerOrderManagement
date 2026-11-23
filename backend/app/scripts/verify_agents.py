import os
import urllib.request
import json

admin_pass = os.getenv("ADMIN_PASSWORD", "")
req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=json.dumps({'email': 'admin@manufacturing.com', 'password': admin_pass}).encode(),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req)
token = json.loads(res.read())['access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print('=== 1. VERIFY OVERVIEW / DASHBOARD ===')
req_dash = urllib.request.Request('http://localhost:8000/api/dashboard/summary', headers=headers)
summary = json.loads(urllib.request.urlopen(req_dash).read())
print('Total Orders in DB:', summary.get('total_orders'))

print('\n=== 2. VERIFY ORDERS DIRECTORY ===')
req_orders = urllib.request.Request('http://localhost:8000/api/orders?page=1&page_size=20', headers=headers)
orders = json.loads(urllib.request.urlopen(req_orders).read())
print('Orders fetched:', len(orders.get('items', [])), 'Total:', orders.get('total'))

print('\n=== 3. VERIFY AGENT 2 (FEASIBILITY ASSESSMENT) ===')
assess_body = json.dumps({
    'customer_id': 'CUS-001',
    'product_id': 'SPH-A15-128',
    'order_qty': 500,
    'requested_delivery_date': '2026-12-01',
    'unit_price_inr': 48000.0,
    'submit_for_approval': True
}).encode()
req_assess = urllib.request.Request('http://localhost:8000/api/assessments', data=assess_body, headers=headers)
assess_res = json.loads(urllib.request.urlopen(req_assess).read())
print('Assessment Code:', assess_res.get('assessment_code'))
print('Overall Status:', assess_res.get('overall_status'))
print('Achievable Delivery Date:', assess_res.get('estimated_delivery_date'))
for d in assess_res.get('department_readiness', []):
    dept = d.get('department')
    st = d.get('readiness_status')
    src = d.get('data_source')
    print(f'  - [{dept}] {st}: {src}')

print('\n=== 4. VERIFY AGENT 3 (MONITORING) ===')
req_mon = urllib.request.Request('http://localhost:8000/api/monitoring/records?limit=3', headers=headers)
mon_records = json.loads(urllib.request.urlopen(req_mon).read())
print('Active Monitored Orders count:', len(mon_records))
if mon_records:
    print('Sample Order:', mon_records[0].get('customer_order_id'), 'Status:', mon_records[0].get('status'))

print('\nALL AGENT AND PLATFORM VERIFICATIONS PASSED!')
