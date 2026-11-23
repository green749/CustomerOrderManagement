import sys
sys.path.append('backend')
from app.config import settings
import httpx

client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=30.0)
login_resp = client.post('/api/auth/login', json={'email': settings.admin_email, 'password': settings.admin_password})
token = login_resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

scenarios = [
    {'name': 'Scenario A: Small 150 Qty, Relaxed Dec 15', 'qty': 150, 'date': '2026-12-15', 'price': 14500},
    {'name': 'Scenario B: Small 150 Qty, Rush Nov 16', 'qty': 150, 'date': '2026-11-16', 'price': 14500},
    {'name': 'Scenario C: Large 1,500 Qty, Dec 15', 'qty': 1500, 'date': '2026-12-15', 'price': 14500},
    {'name': 'Scenario D: Massive 15,000 Qty, Nov 25', 'qty': 15000, 'date': '2026-11-25', 'price': 14500},
]

for s in scenarios:
    res = client.post('/api/assessments', json={
        'customer_id': 'CUS-001',
        'product_id': 'SPH-A15-128',
        'order_qty': s['qty'],
        'requested_delivery_date': s['date'],
        'unit_price_inr': s['price'],
        'priority': 'HIGH',
        'channel': 'PORTAL',
        'submit_for_approval': True
    }, headers=headers)
    d = res.json()
    print('=== ' + s['name'] + ' ===')
    print('ID:', d.get('assessment_id'), '| Status:', d.get('overall_status'))
    print('Requested:', d.get('requested_delivery_date'), '| Achievable:', d.get('estimated_delivery_date'), '| Variance:', d.get('days_variance'), 'days')
    issues = [r['department'] + ': ' + r['readiness_status'] + ' (' + str(r['identified_issue']) + ')' for r in d.get('readiness_records', []) if r['readiness_status'] != 'READY']
    print('Department Issues (' + str(len(issues)) + '):', issues)
    print()
