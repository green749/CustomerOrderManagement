import os, sys
sys.path.insert(0, os.path.abspath("."))

from backend.app.services.agent_db_service import _get_read_only_engine, AGENT_REGISTRY
from sqlalchemy import text

print("--- AGENT DATABASE TELEMETRY INSPECTION ---")
for aid, meta in AGENT_REGISTRY.items():
    eng = _get_read_only_engine(aid)
    if not eng:
        print(f"{aid} ({meta['code']}): NO ENGINE")
        continue
    try:
        with eng.connect() as conn:
            tables = [r[0] for r in conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;")).all()]
            print(f"\n{aid} ({meta['code']} - {meta['name']}):")
            print(f"  Owner: {meta['owner']} | Dept: {meta['department']}")
            print(f"  Total Tables: {len(tables)}")
            
            # Inspect key tables
            for target_table in meta.get("primary_tables", []):
                if target_table in tables:
                    try:
                        cnt = conn.execute(text(f"SELECT count(*) FROM {target_table};")).scalar()
                        print(f"    - {target_table}: {cnt} rows")
                    except Exception as te:
                        print(f"    - {target_table}: error {te}")
                else:
                    print(f"    - {target_table}: NOT FOUND (available: {tables[:3]})")
    except Exception as e:
        print(f"{aid} ({meta['code']}): CONNECTION ERROR {e}")
