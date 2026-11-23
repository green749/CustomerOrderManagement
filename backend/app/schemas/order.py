from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class CustomerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    customer_name: str
    country: str
    segment: str
    service_level: str
    preferred_carrier: str


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    product_family: str
    ram: str
    storage: str
    display: str


class ShipmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shipment_id: str
    customer_order_id: str
    plant_id: str
    carrier: str
    vehicle_type: str
    dispatch_date: date
    planned_eta: datetime
    actual_delivery_ts: Optional[datetime] = None
    shipment_qty: int
    freight_cost_inr: Decimal
    vehicle_utilization_pct: float
    pod_status: str
    shipment_status: str


class OrderRiskInfo(BaseModel):
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    category: str    # ON_SCHEDULE, ACTUAL_DELAY, POTENTIAL_DELAY, UNKNOWN_RISK
    reasons: List[str]
    warnings: List[str] = []


class CustomerOrderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_order_id: str
    customer_id: str
    customer_name: Optional[str] = None
    product_id: str
    product_name: Optional[str] = None
    order_date: date
    requested_delivery_date: date
    confirmed_delivery_date: date
    order_qty: int
    shipped_qty: int
    unit_price_inr: Decimal
    total_value_inr: Decimal
    order_status: str
    priority: str
    channel: str
    risk: Optional[OrderRiskInfo] = None
    link_type: Optional[str] = "UNLINKED"  # DIRECT, INFERRED, UNLINKED
    link_confidence: Optional[str] = None  # HIGH, MEDIUM, LOW, None
    release_status: Optional[str] = "NOT_INSPECTED"  # RELEASED, ON_HOLD, REWORK, SCRAPPED, NOT_INSPECTED
    approved_promise_date: Optional[date] = None
    latest_proposal_status: Optional[str] = None


class CustomerOrderDetail(CustomerOrderListItem):
    customer: Optional[CustomerSummary] = None
    product: Optional[ProductSummary] = None
    shipments: List[ShipmentSummary] = []
    production_orders: List[dict] = []
    data_quality_warnings: List[str] = []
    release_status: str = "NOT_INSPECTED"
    validation: Optional[dict] = None


class OrderTimelineEvent(BaseModel):
    event_type: str  # ORDER_PLACED, CONFIRMED, PRODUCTION_STARTED, QUALITY_CHECK, DISPATCHED, DELIVERED, ALERT
    event_title: str
    timestamp: datetime
    description: str
    status: str
    source_table: str
    metadata: dict = {}


class OrderTimelineResponse(BaseModel):
    customer_order_id: str
    events: List[OrderTimelineEvent]
    total_events: int


class AgentTimelineItem(BaseModel):
    id: str
    category: str  # RISK_ALERT, ACTION, AGENT_RUN, ASSESSMENT, PROPOSAL, DELIVERY_VERDICT
    timestamp: Optional[datetime] = None
    title: str
    department: Optional[str] = None
    severity: Optional[str] = None
    source: Optional[str] = None  # AGENT, RULES, SYSTEM
    status: Optional[str] = None
    action_type: Optional[str] = None
    is_auto_executed: Optional[bool] = None
    approved_by: Optional[str] = None
    proposed_by: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    linked_alert_id: Optional[int] = None
    assessment_id: Optional[str] = None
    overall_status: Optional[str] = None
    estimated_delivery_date: Optional[str] = None
    revised_estimated_date: Optional[str] = None
    promised_date: Optional[str] = None
    delay_days: Optional[int] = None
    verdict: Optional[str] = None
    agent_name: Optional[str] = None
    agent_reasoning: Optional[List[Dict[str, Any]]] = None
    steps_count: Optional[int] = None
    revision: Optional[int] = None
    proposal_id: Optional[int] = None
    reasons: Optional[List[str]] = None
    description: Optional[str] = None
    delivery_impact: Optional[str] = None
    recommended_action: Optional[str] = None


class AgentTimelineResponse(BaseModel):
    customer_order_id: str
    total_events: int
    promised_date: Optional[str] = None
    revised_estimated_date: Optional[str] = None
    delay_days: Optional[int] = None
    verdict: Optional[str] = None
    has_active_revised_proposal: bool = False
    events: List[AgentTimelineItem]
