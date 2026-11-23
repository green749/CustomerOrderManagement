import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    tables_query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in db.execute(tables_query).fetchall()]
    print(f"TOTAL TABLES: {len(tables)}\n")
    
    for t in tables:
        try:
            cnt = db.execute(text(f'SELECT count(*) FROM "{t}";')).scalar()
            print(f"{t}: {cnt} rows")
        except Exception as e:
            print(f"{t}: error ({e})")
finally:
    db.close()
