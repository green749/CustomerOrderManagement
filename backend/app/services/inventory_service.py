from typing import Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from ..repositories.inventory_repo import InventoryRepository
from ..models.business import DimPlant
from ..schemas.inventory import MaterialInventoryItem, MaterialInventorySummary


class InventoryService:
    @staticmethod
    def get_materials(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        plant_id: Optional[str] = None,
        material_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "snapshot_date",
        sort_order: str = "desc",
    ) -> Tuple[List[MaterialInventoryItem], int]:
        records, total = InventoryRepository.list_materials(
            db=db,
            page=page,
            page_size=page_size,
            plant_id=plant_id,
            material_id=material_id,
            warehouse_id=warehouse_id,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Plant names map
        plants = {p.plant_id: p.plant_name for p in db.query(DimPlant).all()}

        items = []
        for r in records:
            available_qty = max(0, r.on_hand_qty - r.allocated_qty - r.blocked_qty - r.quality_hold_qty)
            total_cost = Decimal(r.on_hand_qty) * Decimal(r.unit_cost_inr)

            item = MaterialInventoryItem(
                snapshot_date=r.snapshot_date,
                plant_id=r.plant_id,
                plant_name=plants.get(r.plant_id),
                material_id=r.material_id,
                warehouse_id=r.warehouse_id,
                lot_id=r.lot_id,
                on_hand_qty=r.on_hand_qty,
                allocated_qty=r.allocated_qty,
                blocked_qty=r.blocked_qty,
                quality_hold_qty=r.quality_hold_qty,
                in_transit_qty=r.in_transit_qty,
                safety_stock_qty=r.safety_stock_qty,
                available_qty=available_qty,
                inventory_status=r.inventory_status,
                unit_cost_inr=r.unit_cost_inr,
                total_cost_inr=total_cost,
                expiry_date=r.expiry_date,
            )
            items.append(item)

        return items, total

    @staticmethod
    def get_material_summary(db: Session, material_id: str) -> Optional[MaterialInventorySummary]:
        summary_dict = InventoryRepository.get_material_summary(db, material_id)
        if not summary_dict:
            return None
        return MaterialInventorySummary(**summary_dict)

