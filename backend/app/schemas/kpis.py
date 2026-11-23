from datetime import date, datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class OTIFCustomerKPI(BaseModel):
    total_delivered_orders: int
    orders_with_shipment_milestones: int
    otif_orders_count: int
    otif_rate_pct: float
    verified_shipment_otif_rate_pct: float
    target_otif_pct: float = 95.0
    definition: str = "Orders delivered on or before confirmed delivery date AND in full (shipment_qty >= order_qty) divided by delivered orders."
    data_quality_caveat: str = (
        "Data quality caveat: In the synthetic dataset, all delivered customer orders have recorded shipped_qty < order_qty "
        "in fact_customer_order. Evaluated using actual_delivery_ts and shipment_qty sums from fact_shipment_milestone. "
        "Orders without verified shipment milestone delivery records are excluded from verified OTIF."
    )


class OrderConfirmationTimeKPI(BaseModel):
    average_confirmation_days_proxy: float
    median_confirmation_days_proxy: float
    sample_orders_count: int
    is_proxy: bool = True
    label: str = "Proxy confirmation time: confirmed_delivery_date minus order_date"
    note: str = (
        "Source dataset does not contain separate order acceptance timestamps; "
        "confirmed_delivery_date minus order_date is used as a documented proxy, not actual confirmation processing time."
    )


class ScheduleAdherenceKPI(BaseModel):
    total_production_orders: int
    on_time_production_orders: int
    schedule_adherence_pct: float
    adherence_type: str = "PRODUCTION_SCHEDULE_ADHERENCE"
    definition: str = "Share of manufacturing production orders completed or planned to finish on or before due_date."
    note: str = "Tracks plant production schedule adherence (fact_production_order), distinguished from customer order delivery commitments."


class BacklogAgeingBucket(BaseModel):
    bucket: str  # 0-7 days, 8-14 days, 15-30 days, 30+ days
    order_count: int
    total_quantity: int
    total_value_inr: Decimal


class PromiseDateAccuracyKPI(BaseModel):
    delivered_orders_evaluated: int
    delivered_on_or_before_confirmed: int
    promise_date_accuracy_pct: float
    confirmed_vs_requested_splits: List[Dict[str, Any]]
    definition: str = "Share of delivered orders where actual delivery timestamp is on or before confirmed delivery date."


class ExpediteCostKPI(BaseModel):
    total_expedite_cost_inr: Decimal
    air_cargo_cost_inr: Decimal
    delayed_shipment_cost_inr: Decimal
    expedite_shipment_count: int
    is_proxy: bool = True
    metric_label: str = "Freight Cost Proxy (Expedited / Delayed Shipments)"
    definition: str = "Sum of freight_cost_inr on shipments transported via AIR_CARGO or flagged with shipment_status DELAYED."
    explanation: str = (
        "This figure is a proxy based on total freight costs of air cargo and delayed shipments; "
        "the source dataset does not track dedicated contractual expedite surcharges."
    )


class KPIDashboardResponse(BaseModel):
    as_of_date: date
    customer_id_filter: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    otif: OTIFCustomerKPI
    order_confirmation_time: OrderConfirmationTimeKPI
    schedule_adherence: ScheduleAdherenceKPI
    backlog_ageing: List[BacklogAgeingBucket]
    promise_date_accuracy: PromiseDateAccuracyKPI
    expedite_cost: ExpediteCostKPI


class OverdueOrderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_order_id: str
    customer_id: str
    customer_name: Optional[str] = None
    product_id: str
    product_name: Optional[str] = None
    order_date: date
    confirmed_delivery_date: date
    days_overdue: int
    order_qty: int
    total_value_inr: Decimal
    priority: str
    order_status: str
    release_status: Optional[str] = "NOT_INSPECTED"


class OrderStatusDraftResponse(BaseModel):
    customer_order_id: str
    customer_name: str
    customer_email: Optional[str] = None
    order_status: str
    order_qty: int
    product_name: str
    next_milestone: str
    confirmed_delivery_date: date
    effective_promise_date: date
    identified_risks: List[str]
    is_polished_by_agent: bool
    draft_subject: str
    draft_body: str


class EscalationPackResponse(BaseModel):
    customer_order_id: str
    customer_name: str
    product_name: str
    order_qty: int
    total_value_inr: Decimal
    order_status: str
    confirmed_delivery_date: date
    approved_promise_date: Optional[date] = None
    risk_level: str
    risk_category: str
    release_status: str
    atp_shortages: List[Dict[str, Any]]
    limiting_material_id: Optional[str] = None
    ctp_producible_by: Optional[date] = None
    quality_holds: List[Dict[str, Any]]
    shipment_delays: List[Dict[str, Any]]
    proposed_actions: List[str]
    generated_at: datetime


class CustomerDeliveryPerformance(BaseModel):
    customer_id: str
    customer_name: str
    total_delivered_orders: int
    on_time_delivered_orders: int
    on_time_pct: float


class CarrierDeliveryPerformance(BaseModel):
    carrier: str
    total_shipments: int
    on_time_shipments: int
    delayed_shipments: int
    on_time_pct: float
    avg_transit_days: float


class DeliveryPerformanceResponse(BaseModel):
    customers: List[CustomerDeliveryPerformance]
    carriers: List[CarrierDeliveryPerformance]


class WeeklyTrendItem(BaseModel):
    week_label: str
    week_start_date: date
    total_orders: int
    delivered_orders: int
    otif_rate_pct: float


class WeeklyTrendsResponse(BaseModel):
    trends: List[WeeklyTrendItem]


class AgentPerformanceKPIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auto_approved_on_time_rate: float
    auto_approved_total: int
    auto_approved_on_time: int
    human_approved_on_time_rate: float
    human_approved_total: int
    human_approved_on_time: int
    overall_on_time_rate: float
    total_escalations: int
    avg_alert_resolution_hours: float
    total_resolved_alerts: int


