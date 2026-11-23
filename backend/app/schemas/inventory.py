from datetime import date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class MaterialInventoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_date: date
    plant_id: str
    plant_name: Optional[str] = None
    material_id: str
    warehouse_id: str
    lot_id: str
    on_hand_qty: int
    allocated_qty: int
    blocked_qty: int
    quality_hold_qty: int
    in_transit_qty: int
    safety_stock_qty: int
    available_qty: int
    inventory_status: str
    unit_cost_inr: Decimal
    total_cost_inr: Decimal
    expiry_date: Optional[date] = None


class MaterialInventorySummary(BaseModel):
    material_id: str
    total_on_hand: int
    total_allocated: int
    total_blocked: int
    total_quality_hold: int
    total_in_transit: int
    total_safety_stock: int
    net_available_qty: int
    plants: List[str]
    warehouses: List[str]
    latest_snapshot_date: date
