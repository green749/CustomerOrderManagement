from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MaterialATPItem(BaseModel):
    material_id: str
    material_name: Optional[str] = None
    component_qty_per_unit: float
    scrap_factor: float
    required_qty: float
    usable_qty: float
    shortfall_qty: float
    in_transit_qty: float
    lead_time_days: int
    is_limiting: bool = False


class ATPCheckResult(BaseModel):
    customer_order_id: str
    product_id: str
    order_qty: int
    as_of_date: date
    is_atp_feasible: bool
    limiting_material_id: Optional[str] = None
    max_producible_units: int
    finished_goods_inventory: Dict[str, Any]
    materials: List[MaterialATPItem]
    status: str = "INSUFFICIENT_DATA"
    data_gap_warning: str = (
        "No verified Bill of Materials (BOM) table exists in the connected database. "
        "Material availability calculations are unverified estimates and cannot be presented as verified availability."
    )


class CTPCheckResult(BaseModel):
    customer_order_id: str
    product_id: str
    order_qty: int
    shipped_qty: int
    remaining_qty: int
    standard_cycle_sec: int
    daily_capacity_units: int
    days_to_produce: int
    producible_by: date
    linked_production_orders: List[Dict[str, Any]]
    assumptions: List[str]
    status: str = "INSUFFICIENT_DATA"
    data_gap_warning: Optional[str] = (
        "No verified direct production order linkage exists in manufacturing execution records. "
        "Calculated producible date is an unverified capacity proxy, not a verified production schedule."
    )


class PromiseRecommendationResult(BaseModel):
    customer_order_id: str
    product_id: str
    customer_id: str
    carrier: str
    requested_delivery_date: date
    confirmed_delivery_date: date
    recommended_date: date
    delta_days_vs_confirmed: int
    confidence: str  # HIGH, MEDIUM, LOW
    conflicts: List[str]  # MATERIAL_SHORTAGE, QUALITY_HOLD, CAPACITY, OVERDUE, DATA_GAP
    transit_buffer_days: int
    atp_ready_date: date
    ctp_producible_by: date
    explanations: List[str]
    status: str = "ESTIMATED_RECOMMENDATION"
    data_gap_warning: Optional[str] = (
        "Recommendation relies on unverified BOM estimates and inferred production capacity. "
        "Must be reviewed by an authorized manager before commercial confirmation."
    )


class AllocationItem(BaseModel):
    customer_order_id: str
    customer_id: str
    customer_name: Optional[str] = None
    service_level: str
    priority: str
    requested_delivery_date: date
    order_qty: int
    allocated_qty: int
    unfulfilled_qty: int
    allocation_status: str  # FULL, PARTIAL, UNFULFILLED


class AllocationProposalResponse(BaseModel):
    product_id: Optional[str] = None
    total_usable_inventory_units: int
    total_demanded_units: int
    total_allocated_units: int
    total_unfulfilled_units: int
    allocations: List[AllocationItem]
    status: str = "UNSUPPORTED_DATA"
    data_gap_warning: str = (
        "Inventory snapshot records track raw material IDs (MAT-*), not finished product SKUs (SPH-*). "
        "Finished goods allocation across customer orders is unsupported by source data."
    )

