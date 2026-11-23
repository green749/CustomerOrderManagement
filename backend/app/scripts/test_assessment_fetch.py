import os
import urllib.request
import json

def main():
    try:
        admin_pass = os.getenv("ADMIN_PASSWORD", "")
        req = urllib.request.Request(
            'http://127.0.0.1:8000/api/auth/login',
            data=json.dumps({'email': 'admin@manufacturing.com', 'password': admin_pass}).encode(),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req)
        token = json.loads(res.read())['access_token']
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    except Exception as e:
        print("Login failed:", e)
        return

    req_list = urllib.request.Request('http://127.0.0.1:8000/api/assessments?limit=25', headers=headers)
    try:
        res_list = urllib.request.urlopen(req_list)
        data = json.loads(res_list.read())
        items = data if isinstance(data, list) else data.get('items', [])
        print(f"Total assessments returned: {len(items)}")
        for it in items:
            aid = it.get('assessment_id')
            pname = it.get('product_name')
            cname = it.get('customer_name')
            achievable = it.get('achievable_delivery_date')
            status = it.get('status')
            try:
                req_d = urllib.request.Request(f'http://127.0.0.1:8000/api/assessments/{aid}', headers=headers)
                res_d = urllib.request.urlopen(req_d)
                d_data = json.loads(res_d.read())
                print(f"[OK 200] {aid} ({status}) | Achievable: {achievable} | Cust: {cname} | Prod: {pname}")
            except urllib.error.HTTPError as he:
                print(f"[FAIL {he.code}] {aid}: {he.read().decode('utf-8', errors='ignore')}")
            except Exception as ex:
                print(f"[FAIL ERR] {aid}: {ex}")
    except Exception as e:
        print("Failed listing assessments:", e)

if __name__ == "__main__":
    main()
