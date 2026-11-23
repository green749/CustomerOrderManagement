from datetime import date, datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class CommitmentProposalCreate(BaseModel):
    proposed_date: Optional[date] = None
    recommended_by: str = Field(default="agent", description="agent or user")
    reasons: Optional[List[str]] = Field(default_factory=list)


class CommitmentDecisionRequest(BaseModel):
    decision_note: Optional[str] = None


class CommitmentProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_order_id: str
    proposed_date: date
    recommended_by: str
    reasons: Optional[List[str]] = None
    status: str
    revised_estimated_date: Optional[date] = None
    delay_days: Optional[int] = None
    verdict: Optional[str] = None
    created_by: int
    decided_by: Optional[int] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    revision: int
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime


# ==============================================================================
# AGENT 2 SCHEMAS: ORDER FEASIBILITY & READINESS
# ==============================================================================

class OrderAssessmentCreate(BaseModel):
    customer_id: str = Field(..., description="Customer ID e.g. CUS-001")
    product_id: str = Field(..., description="Product ID e.g. SPH-A15-128")
    order_qty: int = Field(..., gt=0, description="Order quantity")
    requested_delivery_date: date = Field(..., description="Customer requested delivery date")
    unit_price_inr: Optional[float] = Field(None, gt=0, description="Unit price in INR")
    priority: str = Field(default="MEDIUM", description="HIGH, MEDIUM, LOW")
    channel: str = Field(default="EDI", description="EDI, PORTAL, DIRECT")
    ship_to: Optional[str] = Field(None, description="Ship-to address or facility")
    product_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="RAM, storage, color, revisions")
    packaging_req: Optional[str] = Field(None, description="Packaging requirements")
    submit_for_approval: bool = Field(default=True, description="Automatically submit a pending proposal for CS review")


class DepartmentReadinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department: str
    readiness_status: str
    available_evidence: Optional[Dict[str, Any]] = None
    identified_issue: Optional[str] = None
    reason_for_issue: Optional[str] = None
    required_action: Optional[str] = None
    responsible_role: Optional[str] = None
    estimated_delay_days: Optional[int] = None
    data_source: Optional[str] = None
    last_updated_at: datetime
    missing_info: Optional[str] = None


class OrderAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: str
    customer_id: str
    customer_name: Optional[str] = None
    product_id: str
    product_name: Optional[str] = None
    order_qty: int
    requested_delivery_date: date
    unit_price_inr: Optional[float] = None
    priority: str
    channel: str
    ship_to: Optional[str] = None
    product_config: Optional[Dict[str, Any]] = None
    packaging_req: Optional[str] = None
    overall_status: str
    estimated_delivery_date: Optional[date] = None
    days_variance: Optional[int] = None
    confidence_level: str
    blockers_summary: Optional[List[str]] = None
    corrective_actions_summary: Optional[List[str]] = None
    missing_data: Optional[List[str]] = None
    agent_reasoning: Optional[Any] = None
    agent_output: Optional[Any] = None
    agent_disagreement: Optional[bool] = False
    result_source: Optional[str] = "RULES_FALLBACK"
    agent_status: Optional[str] = "rules_mode"
    departments_evaluated: Optional[List[str]] = Field(default_factory=list)
    stopped_early: Optional[bool] = False
    stop_reason: Optional[str] = None
    revised_estimated_date: Optional[date] = None
    delay_days: Optional[int] = None
    verdict: Optional[str] = None
    proposal_id: Optional[int] = None
    proposal: Optional[CommitmentProposalResponse] = None
    customer_order_id: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    readiness_records: List[DepartmentReadinessResponse] = Field(default_factory=list)


# ==============================================================================
# AGENT 3 SCHEMAS: ORDER MONITORING & RISK ALERTS
# ==============================================================================

class OrderMonitoringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_order_id: str
    approved_delivery_date: date
    status: str
    baseline_milestones: Optional[Dict[str, Any]] = None
    started_at: datetime
    last_checked_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    closure_reason: Optional[str] = None
    created_at: datetime
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    order_qty: Optional[int] = None
    open_alerts_count: Optional[int] = 0


class RiskAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_order_id: str
    monitoring_record_id: Optional[int] = None
    department: str
    risk_category: str
    severity: str
    title: str
    description: str
    delivery_impact: Optional[str] = None
    recommended_action: Optional[str] = None
    status: str
    result_source: Optional[str] = "RULES_FALLBACK"
    assigned_owner: Optional[str] = None
    dedup_fingerprint: str
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    customer_communicated: bool = False
    customer_communication_notes: Optional[str] = None
    customer_communicated_at: Optional[datetime] = None
    customer_communicated_by: Optional[int] = None
    first_email_sent_at: Optional[datetime] = None
    days_unresolved: Optional[int] = None
    is_followup_due: bool = False
    followup_sent_at: Optional[datetime] = None
    followup_count: int = 0


class AlertAssignRequest(BaseModel):
    assigned_owner: str = Field(..., min_length=2, description="Name or role of the assignee")


class AlertResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=2, description="Actions taken to resolve the risk")


class EmailNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: Optional[int] = None
    customer_order_id: str
    recipient_email: str
    recipient_category: str = "OPERATIONAL"
    notification_type: str = "ACTION_REQUIRED"
    department: str
    subject: str
    body_text: str
    status: str
    retry_count: int
    failure_reason: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime
    last_attempt_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class DepartmentContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department: str
    role_name: str
    email: str
    is_active: bool


# ==============================================================================
# AGENT 3 CORRECTIVE ACTIONS SCHEMAS
# ==============================================================================

class AgentActionDecisionRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Optional justification or decision reason")


class AgentActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: Optional[int] = None
    customer_order_id: str
    action_type: str
    parameters: Optional[Dict[str, Any]] = None
    status: str
    requires_approval: bool
    proposed_by: str
    approved_by: Optional[int] = None
    executed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    customer_order_id: str
    assessment_id: Optional[str] = None
    alert_id: Optional[int] = None
    status: str
    provider: str
    steps: Optional[Any] = None
    final_output: Optional[Any] = None
    llm_calls: int = 0
    created_at: datetime




