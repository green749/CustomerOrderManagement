from typing import List, Dict, Optional
from pydantic import BaseModel
from decimal import Decimal
from .order import OrderRiskInfo


class DashboardSummary(BaseModel):
    total_orders: int
    open_orders: int
    in_production_orders: int
    partially_shipped_orders: int
    delivered_orders: int
    delayed_orders_count: int
    potential_delay_count: int
    unknown_risk_count: int
    total_order_value_inr: Decimal
    total_shipped_value_inr: Decimal
    on_time_delivery_rate_pct: float
    data_quality_missing_po_count: int


class OrderStatusCount(BaseModel):
    status: str
    count: int
    percentage: float
    total_qty: int
    total_value_inr: Decimal


class AtRiskOrderItem(BaseModel):
    customer_order_id: str
    customer_name: str
    product_name: str
    order_status: str
    priority: str
    confirmed_delivery_date: str
    order_qty: int
    shipped_qty: int
    risk: OrderRiskInfo
    link_type: Optional[str] = "UNLINKED"
    link_confidence: Optional[str] = None
    release_status: Optional[str] = "NOT_INSPECTED"


class AtRiskSummaryResponse(BaseModel):
    total_at_risk: int
    actual_delayed: int
    potential_delayed: int
    unknown_risk: int
    items: List[AtRiskOrderItem]


class PlantPerformanceItem(BaseModel):
    plant_id: str
    plant_name: str
    total_pos: int
    completed: int
    in_progress: int
    total_units: int
    adherence_pct: float


class ProductDemandItem(BaseModel):
    product_id: str
    product_name: str
    total_orders: int
    total_demand_units: int
    total_revenue_inr: float


class CarrierMetricItem(BaseModel):
    carrier: str
    total_shipments: int
    on_time_shipments: int
    delayed_shipments: int
    on_time_pct: float
    avg_utilization_pct: float


class QualityYieldSummary(BaseModel):
    total_inspections: int
    release_count: int
    hold_count: int
    scrap_count: int
    yield_pct: float


class DepartmentRiskMetric(BaseModel):
    department: str
    total_alerts: int
    critical_count: int
    open_count: int


class CustomerFulfillmentMetric(BaseModel):
    customer_id: str
    customer_name: str
    segment: str
    total_orders: int
    delivered_orders: int
    in_production_orders: int
    pending_orders: int
    total_units: int
    total_value_inr: float


class PromiseAccuracySplit(BaseModel):
    split: str
    count: int
    percentage: float


class BacklogAgeingMetric(BaseModel):
    bucket: str
    order_count: int
    total_quantity: int
    total_value_inr: float


class AnalyticsDashboardResponse(BaseModel):
    plant_performance: List[PlantPerformanceItem]
    product_demand: List[ProductDemandItem]
    carrier_performance: List[CarrierMetricItem]
    quality_yield: QualityYieldSummary
    department_risks: List[DepartmentRiskMetric]
    customer_fulfillment: List[CustomerFulfillmentMetric]
    promise_accuracy_splits: List[PromiseAccuracySplit]
    backlog_ageing: List[BacklogAgeingMetric]


class CustomerProgressSummaryItem(BaseModel):
    customer_name: str
    total_orders: int
    delivered_count: int
    in_production_count: int
    partially_shipped_count: int
    open_count: int
    avg_progress_pct: float
    next_delivery_date: Optional[str] = None


class OrderProgressItem(BaseModel):
    order_id: str
    customer_name: str
    product_name: str
    order_qty: int
    status: str
    delivery_date: Optional[str] = None
    progress_pct: int
    health: str


class CustomerOrdersProgressResponse(BaseModel):
    customers: List[CustomerProgressSummaryItem]
    orders: List[OrderProgressItem]



