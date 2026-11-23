from app.database import SessionLocal
from app.models.workflow import OrderMonitoringRecord, CommitmentProposal
from app.models.business import FactCustomerOrder

db = SessionLocal()
recs = db.query(OrderMonitoringRecord).all()
print(f"Total monitoring records: {len(recs)}")

pending_orders_in_monitoring = []
for r in recs:
    co = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == r.customer_order_id).first()
    prop = db.query(CommitmentProposal).filter(CommitmentProposal.customer_order_id == r.customer_order_id).order_by(CommitmentProposal.revision.desc()).first()
    
    co_status = co.order_status if co else "UNKNOWN"
    prop_status = prop.status if prop else "NO_PROPOSAL"
    
    is_pending = (
        co_status in ["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING"]
        or prop_status == "PENDING"
    )
    if is_pending:
        pending_orders_in_monitoring.append((r.id, r.customer_order_id, r.status, co_status, prop_status))

print(f"\nOrders with monitoring records that are PENDING APPROVAL ({len(pending_orders_in_monitoring)}):")
for p in pending_orders_in_monitoring:
    print(f"  Record #{p[0]}: order={p[1]}, mon_status={p[2]}, order_status={p[3]}, prop_status={p[4]}")

db.close()
