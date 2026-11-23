import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.app.services.agent_db_service import _get_read_only_engine
from sqlalchemy import text

targets = [
    ("AGENT_01", "fact_production_plan"),
    ("AGENT_01", "dim_work_center"),
    ("AGENT_03", "downtime_events"),
    ("AGENT_03", "oee_daily_snapshots"),
    ("AGENT_07", "ecr_requests"),
    ("AGENT_07", "eco_orders"),
    ("AGENT_08", "component_trace"),
    ("AGENT_08", "lot_history"),
    ("AGENT_10", "supplier_scorecards"),
    ("AGENT_12", "carrier_dispatches"),
    ("AGENT_12", "transit_milestones"),
    ("AGENT_16", "unit_cogs_breakdown"),
]

for aid, table in targets:
    eng = _get_read_only_engine(aid)
    if not eng:
        continue
    try:
        with eng.connect() as conn:
            cols = [r[0] for r in conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' LIMIT 12;")).all()]
            print(f"{aid}.{table}: {cols}")
            row = conn.execute(text(f"SELECT * FROM {table} LIMIT 1;")).mappings().first()
            if row:
                print(f"   Sample: {dict(row)}")
    except Exception as e:
        print(f"{aid}.{table}: error {e}")
