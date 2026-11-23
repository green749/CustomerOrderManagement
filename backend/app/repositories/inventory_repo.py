from typing import Optional, List, Tuple
from sqlalchemy import func, desc, asc
from sqlalchemy.orm import Session
from ..models.business import FactInventoryDailySnapshot, DimPlant


class InventoryRepository:
    @staticmethod
    def list_materials(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        plant_id: Optional[str] = None,
        material_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "snapshot_date",
        sort_order: str = "desc",
    ) -> Tuple[List[FactInventoryDailySnapshot], int]:
        query = db.query(FactInventoryDailySnapshot)

        if plant_id:
            query = query.filter(FactInventoryDailySnapshot.plant_id == plant_id)
        if material_id:
            query = query.filter(FactInventoryDailySnapshot.material_id == material_id)
        if warehouse_id:
            query = query.filter(FactInventoryDailySnapshot.warehouse_id == warehouse_id)
        if status:
            query = query.filter(FactInventoryDailySnapshot.inventory_status == status.upper())

        total = query.count()

        sort_col = getattr(FactInventoryDailySnapshot, sort_by, FactInventoryDailySnapshot.snapshot_date)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))

        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def get_material_summary(db: Session, material_id: str) -> Optional[dict]:
        latest_date = (
            db.query(func.max(FactInventoryDailySnapshot.snapshot_date))
            .filter(FactInventoryDailySnapshot.material_id == material_id)
            .scalar()
        )
        if not latest_date:
            return None

        records = (
            db.query(FactInventoryDailySnapshot)
            .filter(
                FactInventoryDailySnapshot.material_id == material_id,
                FactInventoryDailySnapshot.snapshot_date == latest_date,
            )
            .all()
        )

        total_on_hand = sum(r.on_hand_qty for r in records)
        total_allocated = sum(r.allocated_qty for r in records)
        total_blocked = sum(r.blocked_qty for r in records)
        total_quality_hold = sum(r.quality_hold_qty for r in records)
        total_in_transit = sum(r.in_transit_qty for r in records)
        total_safety_stock = sum(r.safety_stock_qty for r in records)
        net_available = total_on_hand - total_allocated - total_blocked - total_quality_hold

        plants = sorted(list({r.plant_id for r in records}))
        warehouses = sorted(list({r.warehouse_id for r in records}))

        return {
            "material_id": material_id,
            "total_on_hand": total_on_hand,
            "total_allocated": total_allocated,
            "total_blocked": total_blocked,
            "total_quality_hold": total_quality_hold,
            "total_in_transit": total_in_transit,
            "total_safety_stock": total_safety_stock,
            "net_available_qty": max(0, net_available),
            "plants": plants,
            "warehouses": warehouses,
            "latest_snapshot_date": latest_date,
        }

