import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    for tbl in ["order_assessments", "risk_alerts", "commitment_proposals"]:
        cols = db.execute(text(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{tbl}'
            ORDER BY ordinal_position;
        """)).fetchall()
        print(f"\n--- {tbl} ---")
        for c, t in cols:
            print(f"  {c} ({t})")
finally:
    db.close()
