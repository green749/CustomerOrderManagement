import sys
import os
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Find data folder
data_dir = Path(r"c:\Users\DELL 5430\Desktop\Manufacturing\data\data")
if not data_dir.exists():
    data_dir = Path(r"c:\Users\DELL 5430\Desktop\Manufacturing\data")

print(f"Reading CSVs from: {data_dir}\n")

csv_files = sorted(list(data_dir.glob("*.csv")))

results = []
for csv_path in csv_files:
    table_name = csv_path.stem
    try:
        df = pd.read_csv(csv_path)
        csv_rows = len(df)
    except Exception as e:
        csv_rows = f"Error reading: {e}"
        
    try:
        db_rows = db.execute(text(f'SELECT count(*) FROM "{table_name}";')).scalar()
    except Exception as e:
        db_rows = "Table not in DB"
        
    match = (csv_rows == db_rows) if isinstance(csv_rows, int) and isinstance(db_rows, int) else False
    results.append({
        "file": csv_path.name,
        "table": table_name,
        "csv_rows": csv_rows,
        "db_rows": db_rows,
        "matched": match
    })

db.close()

print(f"{'CSV File':<32} | {'Table Name':<30} | {'CSV Rows':<10} | {'DB Rows':<10} | Match?")
print("-" * 95)
for r in results:
    status = "YES" if r["matched"] else ("PARTIAL (Duplicates handled)" if r["db_rows"] != "Table not in DB" else "NO")
    print(f"{r['file']:<32} | {r['table']:<30} | {str(r['csv_rows']):<10} | {str(r['db_rows']):<10} | {status}")
