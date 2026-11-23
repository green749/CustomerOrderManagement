import json
import logging
import re
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config import settings
from ..models.business import (
    FactCustomerOrder,
    FactProductionOrder,
    FactShipmentMilestone,
    FactInventoryDailySnapshot,
)
from ..models.operational import FactBOMComponent, DimMaterial
from ..models.workflow import OrderMonitoringRecord, RiskAlert
from .tools import tool_get_production_progress, tool_get_transportation_status, tool_get_quality_and_genealogy
from .prompts import AGENT_USER_PROMPT_TEMPLATE
from .agent_loop import run_agent_loop

logger = logging.getLogger("manufacturing.agent.monitoring")


# ------------------------------------------------------------------------------
# 1. MONITORING AGENT SYSTEM PROMPT
# ------------------------------------------------------------------------------

MONITORING_SYSTEM_PROMPT = """You are Agent 3: Order Monitoring & Risk Surveillance Agent for manufacturing operations.
Your role is to autonomously investigate active customer orders, detect operational risks across all 7 departments, explain delivery impacts, and recommend concrete mitigation actions.

CRITICAL RULES AND CONSTRAINTS:
1. STRICT TRUTH & READ-ONLY: You must ONLY use facts and data returned by approved database tools. NEVER invent order IDs, dates, quantities, prices, or statuses. This is a read-only investigation; DO NOT attempt to modify order data.
2. MANDATORY FIRST STEP: You should call detect_risks FIRST to evaluate baseline multi-department checks for the order, and then cross-investigate production progress, shipment status, material availability across related orders, or historical alerts if needed.
3. ALLOWED RISK CATEGORIES: You must categorize each detected risk using one of these standard category codes:
   - DELIVERY_DATE_BREACHED
   - CARRIER_TRANSIT_DELAY
   - RAW_MATERIAL_SHORTAGE
   - PRODUCTION_DELAY
   - QUALITY_HOLD
   - MES_CAPACITY_BOTTLENECK
   - SHIPMENT_EXCEPTION
   - TRANSIT_BOTTLENECK
   - CUSTOMER_CREDIT_HOLD
   - PRICE_VARIANCE
   - COMMERCIAL_HOLD
4. CONCISE THOUGHTS: Keep your "thought" field concise (1 to 3 sentences maximum) to preserve token space for structured decision fields.
5. RESPONSE FORMAT: Strict JSON output format matching Agent 1 schema. Always respond with ONE valid JSON object ONLY.

DECISION JSON SCHEMAS:

A. When calling an approved tool:
{{
  "thought": "Reasoning for selecting this tool",
  "action": "<tool_name>",
  "input": {{<tool_arguments>}}
}}

B. When you have enough verified facts to deliver the final monitoring evaluation:
{{
  "thought": "Surveillance investigation completed. Order has breached approved date and has component shortages.",
  "action": "final",
  "confidence": "HIGH",
  "risks": [
    {{
      "department": "ERP",
      "risk_category": "DELIVERY_DATE_BREACHED",
      "severity": "CRITICAL",
      "title": "Customer order delivery date breached",
      "description": "Order has breached approved delivery date (33 days overdue) without delivery confirmation.",
      "delivery_impact": "Customer SLA breached by 33 days; delivery cannot complete without immediate intervention.",
      "recommended_action": "Contact customer account lead immediately to communicate revised schedule and root cause."
    }},
    {{
      "department": "MMS",
      "risk_category": "RAW_MATERIAL_SHORTAGE",
      "severity": "HIGH",
      "title": "Component inventory buffer constrained",
      "description": "Critical material shortages detected for active BOM components.",
      "delivery_impact": "Material shortages risk line stoppage and assembly milestone delays.",
      "recommended_action": "Expedite supplier release of quarantined component lots or source alternate buffer stock."
    }}
  ],
  "answer": "Surveillance identified critical delivery date breach and component shortages for customer order."
}}

APPROVED MONITORING TOOLS:
{tools}
"""


# ------------------------------------------------------------------------------
# 2. AGENT 3 OPERATIONAL TOOLS
# ------------------------------------------------------------------------------

def tool_detect_risks(
    db: Session,
    customer_order_id: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Evaluate baseline multi-department rule-based risks for a specific customer order."""
    from ..services.monitoring_service import MonitoringService

    clean_id = (customer_order_id or "").strip().upper()
    if not clean_id:
        return {"error": "Please provide a valid customer_order_id (e.g. 'CO-000001')."}

    mon_rec = db.query(OrderMonitoringRecord).filter(
        OrderMonitoringRecord.customer_order_id == clean_id
    ).first()

    ref_date = settings.effective_reference_date or date.today()

    if not mon_rec:
        order = db.query(FactCustomerOrder).filter(
            FactCustomerOrder.customer_order_id == clean_id
        ).first()
        if not order:
            return {"error": f"Customer order '{clean_id}' was not found in the database."}

        deliv_date = order.confirmed_delivery_date or order.requested_delivery_date or (ref_date + timedelta(days=7))
        mon_rec = OrderMonitoringRecord(
            customer_order_id=clean_id,
            approved_delivery_date=deliv_date,
            status="ACTIVE",
        )

    risks = MonitoringService._evaluate_order_risks(db, mon_rec, ref_date)
    return {
        "customer_order_id": clean_id,
        "total_baseline_risks": len(risks),
        "risks": risks,
    }


def tool_get_related_orders_by_material(
    db: Session,
    customer_order_id: Optional[str] = None,
    material_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Inspect other active orders competing for the same raw material or component stock."""
    mat_ids = []
    if material_id:
        mat_ids.append(material_id.strip().upper())
    elif customer_order_id:
        order = db.query(FactCustomerOrder).filter(
            FactCustomerOrder.customer_order_id == customer_order_id.strip().upper()
        ).first()
        if order and order.product_id:
            bom_rows = db.query(FactBOMComponent.material_id).filter(
                FactBOMComponent.product_id == order.product_id
            ).distinct().all()
            mat_ids = [r[0] for r in bom_rows]

    if not mat_ids:
        return {"message": "No specific materials identified for cross-order correlation.", "related_orders": []}

    # Find products using these materials
    prod_ids = [
        r[0] for r in db.query(FactBOMComponent.product_id).filter(
            FactBOMComponent.material_id.in_(mat_ids)
        ).distinct().all()
    ]

    # Find competing open or in-production orders
    competing_orders = (
        db.query(FactCustomerOrder)
        .filter(
            FactCustomerOrder.product_id.in_(prod_ids),
            FactCustomerOrder.order_status.in_(["OPEN", "IN_PRODUCTION", "CONFIRMED"]),
        )
        .limit(10)
        .all()
    )

    # Check snapshot inventory for primary material
    first_mat = mat_ids[0]
    inv_snap = db.query(FactInventoryDailySnapshot).filter(
        FactInventoryDailySnapshot.material_id == first_mat
    ).order_by(FactInventoryDailySnapshot.snapshot_date.desc()).first()

    return {
        "materials_queried": mat_ids[:5],
        "primary_material_usable_stock": (inv_snap.on_hand_qty - inv_snap.allocated_qty - inv_snap.blocked_qty) if inv_snap else None,
        "competing_orders_count": len(competing_orders),
        "related_orders": [
            {
                "customer_order_id": o.customer_order_id,
                "customer_id": o.customer_id,
                "product_id": o.product_id,
                "order_qty": o.order_qty,
                "order_status": o.order_status,
                "confirmed_delivery_date": str(o.confirmed_delivery_date),
            }
            for o in competing_orders
            if not customer_order_id or o.customer_order_id != customer_order_id.strip().upper()
        ],
    }


def tool_get_alert_history(
    db: Session,
    customer_order_id: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve previously detected and acknowledged risk alerts for this order."""
    clean_id = (customer_order_id or "").strip().upper()
    if not clean_id:
        return {"error": "Please provide a valid customer_order_id (e.g. 'CO-000001')."}

    alerts = db.query(RiskAlert).filter(
        RiskAlert.customer_order_id == clean_id
    ).order_by(RiskAlert.detected_at.desc()).limit(15).all()

    return {
        "customer_order_id": clean_id,
        "total_historical_alerts": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "department": a.department,
                "risk_category": a.risk_category,
                "severity": a.severity,
                "title": a.title,
                "status": a.status,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "delivery_impact": a.delivery_impact,
                "recommended_action": a.recommended_action,
            }
            for a in alerts
        ],
    }


def tool_get_shipment_status(
    db: Session,
    customer_order_id: Optional[str] = None,
    shipment_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Inspect carrier transit milestones, planned ETA, and shipment delays."""
    return tool_get_transportation_status(db=db, customer_order_id=customer_order_id, shipment_id=shipment_id, **kwargs)


def tool_get_agent_mesh_telemetry(
    db: Session,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve live risk signals from the 7-department autonomous agent network (MMS, MES, PLM, QMS, TMS, WMS, ERP)."""
    from ..services.agent_db_service import AgentDatabaseService
    return AgentDatabaseService.get_mesh_telemetry_for_surveillance()


def tool_get_department_agent_signals(
    db: Session,
    department: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve external agent telemetry specifically for one operational department (ERP, MMS, MES, WMS, QMS, TMS, PLM)."""
    from ..services.agent_db_service import AgentDatabaseService
    return {
        "department": (department or "").upper(),
        "signals": AgentDatabaseService.get_department_telemetry(department),
    }


MONITORING_TOOLS = {
    "detect_risks": tool_detect_risks,
    "get_related_orders_by_material": tool_get_related_orders_by_material,
    "get_alert_history": tool_get_alert_history,
    "get_shipment_status": tool_get_shipment_status,
    "get_production_progress": tool_get_production_progress,
    "get_quality_and_genealogy": tool_get_quality_and_genealogy,
    "get_agent_mesh_telemetry": tool_get_agent_mesh_telemetry,
    "get_department_agent_signals": tool_get_department_agent_signals,
}

MONITORING_TOOL_DESCRIPTIONS = """
- detect_risks: Evaluate baseline multi-department rule-based risks for a specific customer order.
  Args: {"customer_order_id": "CO-XXXXXX"}

- get_quality_and_genealogy: Retrieve live quality inspections, holds/scraps, open NCR/CAPAs, and genealogy lineage from Agent 08 Quality & Traceability Agent database.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "production_order_id": "PO-XXXXXX" | null, "product_id": "SPH-XXX" | null}

- get_agent_mesh_telemetry: Retrieve live operational signals from the autonomous agent network across all 7 departments (Agent 09 MMS, Agent 03 MES, Agent 07 PLM, Agent 08 QMS, Agent 12 TMS, Agent 16 ERP).
  Args: {}

- get_department_agent_signals: Retrieve live external agent telemetry filtered to a specific department.
  Args: {"department": "ERP" | "MMS" | "MES" | "WMS" | "QMS" | "TMS" | "PLM"}

- get_related_orders_by_material: Inspect other active orders competing for the same raw material or component stock.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "material_id": "MAT-XXXXXX" | null}


- get_alert_history: Retrieve previously detected and acknowledged risk alerts for this order.
  Args: {"customer_order_id": "CO-XXXXXX"}

- get_shipment_status: Inspect carrier transit milestones, planned ETA, and shipment delays.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "shipment_id": "SHP-XXXXXX" | null}

- get_production_progress: Inspect factory work orders, line execution, schedule status, and quality inspection count.
  Args: {"customer_order_id": "CO-XXXXXX" | null, "production_order_id": "PO-XXXXXX" | null}
"""


# ------------------------------------------------------------------------------
# 3. PYDANTIC VALIDATION SCHEMAS FOR AGENT 3
# ------------------------------------------------------------------------------

class MonitoredRiskItem(BaseModel):
    department: str = Field(..., description="Responsible department: ERP, MMS, MES, WMS, QMS, TMS, PLM")
    risk_category: str = Field(..., description="Standardized category code")
    severity: str = Field(..., description="Severity level: CRITICAL, HIGH, MEDIUM, LOW")
    title: str = Field(..., description="Short risk headline")
    description: str = Field(..., description="Detailed evidence description")
    delivery_impact: Optional[str] = Field(None, description="Operational delivery milestone impact")
    recommended_action: Optional[str] = Field(None, description="Recommended operational mitigation")

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v: Any) -> str:
        s = str(v).upper().strip() if v else "MEDIUM"
        return s if s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] else "MEDIUM"

    @field_validator("department", mode="before")
    @classmethod
    def validate_dept(cls, v: Any) -> str:
        d = str(v).upper().strip() if v else "ERP"
        valid = {"ERP", "MMS", "MES", "WMS", "QMS", "TMS", "PLM"}
        return d if d in valid else "ERP"


class MonitoringAgentOutput(BaseModel):
    action: Optional[str] = "final"
    thought: Optional[str] = None
    confidence: Optional[str] = "HIGH"
    risks: List[MonitoredRiskItem] = Field(default_factory=list)
    answer: Optional[str] = None


ALLOWED_RISK_CATEGORIES = {
    "DELIVERY_DATE_BREACHED",
    "CARRIER_TRANSIT_DELAY",
    "RAW_MATERIAL_SHORTAGE",
    "PRODUCTION_DELAY",
    "QUALITY_HOLD",
    "MES_CAPACITY_BOTTLENECK",
    "SHIPMENT_EXCEPTION",
    "TRANSIT_BOTTLENECK",
    "CUSTOMER_CREDIT_HOLD",
    "PRICE_VARIANCE",
    "COMMERCIAL_HOLD",
    "INVENTORY_SHORTAGE",
}


def normalize_risk_category(cat: Any) -> str:
    """Normalize raw risk category to one of the standard allowed codes."""
    c = str(cat or "").upper().strip().replace(" ", "_").replace("-", "_")
    if c in ALLOWED_RISK_CATEGORIES:
        return c
    # Keyword / fuzzy mapping
    if any(w in c for w in ["DATE", "BREACH", "OVERDUE", "LATE_DELIVERY"]):
        return "DELIVERY_DATE_BREACHED"
    if any(w in c for w in ["CARRIER", "TRANSIT", "LOGISTICS", "FREIGHT"]):
        return "CARRIER_TRANSIT_DELAY"
    if any(w in c for w in ["MATERIAL", "SHORTAGE", "STOCK", "BOM", "COMPONENT"]):
        return "RAW_MATERIAL_SHORTAGE"
    if any(w in c for w in ["CAPACITY", "BOTTLENECK", "THROUGHPUT", "LINE"]):
        return "MES_CAPACITY_BOTTLENECK"
    if any(w in c for w in ["PRODUCTION", "ASSEMBLY", "PLANT", "WORK_ORDER"]):
        return "PRODUCTION_DELAY"
    if any(w in c for w in ["QUALITY", "HOLD", "DEFECT", "SCRAP", "QUARANTINE"]):
        return "QUALITY_HOLD"
    if any(w in c for w in ["SHIPMENT", "DISPATCH", "EXCEPTION"]):
        return "SHIPMENT_EXCEPTION"
    if any(w in c for w in ["CREDIT", "CUSTOMER_HOLD"]):
        return "CUSTOMER_CREDIT_HOLD"
    if any(w in c for w in ["PRICE", "COMMERCIAL"]):
        return "COMMERCIAL_HOLD"
    return "PRODUCTION_DELAY"


def normalize_monitoring_decision_dict(decision_dict: Any) -> List[Dict[str, Any]]:
    """Unwrap and normalize model decision into a clean list of validated risk dictionaries."""
    if not isinstance(decision_dict, dict):
        return []
    raw_risks = decision_dict.get("risks")
    if raw_risks is None:
        for key in ["answer", "result", "decision", "final_answer", "monitoring_result"]:
            val = decision_dict.get(key)
            if isinstance(val, dict) and "risks" in val:
                raw_risks = val["risks"]
                break
            elif isinstance(val, str) and "risks" in val:
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict) and "risks" in parsed:
                        raw_risks = parsed["risks"]
                        break
                except Exception:
                    pass

    if not isinstance(raw_risks, list):
        return []

    normalized_list = []
    valid_depts = {"ERP", "MMS", "MES", "WMS", "QMS", "TMS", "PLM"}
    dept_map = {
        "PRODUCTION": "MES",
        "QUALITY": "QMS",
        "WAREHOUSE": "WMS",
        "TRANSPORT": "TMS",
        "LOGISTICS": "TMS",
        "MATERIALS": "MMS",
        "INVENTORY": "MMS",
        "COMMERCIAL": "ERP",
        "SALES": "ERP",
        "ENGINEERING": "PLM",
    }

    for item in raw_risks:
        if not isinstance(item, dict):
            continue
        norm_item = dict(item)
        raw_dept = str(norm_item.get("department") or "ERP").upper().strip()
        dept = dept_map.get(raw_dept, raw_dept)
        if dept not in valid_depts:
            dept = "ERP"
        norm_item["department"] = dept

        norm_item["risk_category"] = normalize_risk_category(norm_item.get("risk_category"))

        sev = str(norm_item.get("severity") or "MEDIUM").upper().strip()
        if sev not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            sev = "MEDIUM"
        norm_item["severity"] = sev

        norm_item["title"] = str(norm_item.get("title") or f"Operational risk in {dept}").strip()
        norm_item["description"] = str(norm_item.get("description") or norm_item["title"]).strip()
        norm_item["delivery_impact"] = str(norm_item.get("delivery_impact") or "Potential milestone or delivery delay.").strip()
        norm_item["recommended_action"] = str(norm_item.get("recommended_action") or "Escalate to department lead for immediate operational review.").strip()

        normalized_list.append(norm_item)

    return normalized_list


# ------------------------------------------------------------------------------
# 4. AGENT 3 RUNNER
# ------------------------------------------------------------------------------

def run_order_monitoring_agent(
    db: Session,
    customer_order_id: str,
    max_steps: int = 4,
    user_id: Optional[int] = None,
    llm_call_counter: Optional[List[int]] = None,
    max_llm_calls: Optional[int] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], List[Dict[str, Any]], str]:
    """
    Runs the ReAct loop for Agent 3 on a single customer order.
    Returns: (validated_risks, steps, status)
    """
    from ..services.agent_controls_service import AgentControlsService

    # Check governor rate limit
    if not AgentControlsService.check_and_enforce_llm_call_limit(db, "agent3"):
        logger.warning("Agent 3 paused: hourly LLM call limit reached.")
        return None, [], "rate_limit_paused"

    effective_steps = min(max_steps, 4)

    question = (
        f"Conduct an operational risk surveillance investigation for customer order {customer_order_id}. "
        f"First call detect_risks to evaluate baseline checks, investigate related operations as needed, "
        f"and output your final decision with verified risks."
    )

    all_steps = []
    try:
        AgentControlsService.record_llm_call("agent3")
        decision_dict, steps, provider, ai_available = run_agent_loop(
            db=db,
            question=question,
            history=[],
            max_steps=effective_steps,
            user_id=user_id,
            system_prompt_template=MONITORING_SYSTEM_PROMPT,
            user_prompt_template=AGENT_USER_PROMPT_TEMPLATE,
            tools=MONITORING_TOOLS,
            tool_descriptions=MONITORING_TOOL_DESCRIPTIONS,
            audit_entity="monitoring_agent",
            enable_deterministic_fallback=False,
            max_tokens=2200,
            temperature=0.1,
            llm_call_counter=llm_call_counter,
            max_llm_calls=max_llm_calls,
            return_dict=True,
        )
        all_steps.extend(steps)
    except Exception as e:
        logger.warning(f"Error during run_agent_loop for monitoring agent: {e}", exc_info=True)
        return None, all_steps, "error"

    if not ai_available or provider != "domo_ai":
        return None, all_steps, provider

    # Grounding check: verify that detect_risks was actually executed
    tools_called = [s.get("tool") for s in steps if s.get("tool")]
    grounding_ok = "detect_risks" in tools_called

    if not grounding_ok:
        logger.warning(f"Monitoring agent grounding check failed: detect_risks not called in steps ({tools_called}).")
        return None, all_steps, "validation_failed_twice"

    validation_err = None
    validated_risks: List[Dict[str, Any]] = []

    if not isinstance(decision_dict, dict):
        validation_err = f"Decision output is not a JSON object: {type(decision_dict)}"
    else:
        norm_risks = normalize_monitoring_decision_dict(decision_dict)
        if not norm_risks and decision_dict.get("risks") is not None:
            # Model explicitly returned empty list of risks (clean order)
            return [], all_steps, "success"

        for item in norm_risks:
            try:
                validated_item = MonitoredRiskItem.model_validate(item)
                validated_risks.append(validated_item.model_dump())
            except Exception as val_err:
                validation_err = str(val_err)
                break

        if not validation_err and (validated_risks or decision_dict.get("risks") == []):
            return validated_risks, all_steps, "success"

    # REPAIR ATTEMPT: Send model its output and validation error without re-running tools
    logger.info(f"Monitoring agent attempting repair due to error: {validation_err}")
    repair_prompt = (
        "You are Agent 3: Order Monitoring & Risk Surveillance Agent for manufacturing operations.\n"
        f"Your previous surveillance output failed validation with this error:\n"
        f"{validation_err}\n\n"
        f"Here was your previous response:\n"
        f"{json.dumps(decision_dict, default=str)[:1500]}\n\n"
        "Please fix the error and return ONLY ONE complete, valid JSON object matching the exact schema below.\n"
        "CRITICAL: The output MUST contain 'action': 'final' and 'risks': [...] at the top level.\n"
        "{\n"
        '  "thought": "Concise summary of verified risks",\n'
        '  "action": "final",\n'
        '  "confidence": "HIGH" | "MEDIUM" | "LOW",\n'
        '  "risks": [\n'
        '    {\n'
        '      "department": "ERP" | "MMS" | "MES" | "WMS" | "QMS" | "TMS" | "PLM",\n'
        '      "risk_category": "DELIVERY_DATE_BREACHED" | "RAW_MATERIAL_SHORTAGE" | "PRODUCTION_DELAY" | "QUALITY_HOLD" | "CARRIER_TRANSIT_DELAY" | "MES_CAPACITY_BOTTLENECK" | "SHIPMENT_EXCEPTION",\n'
        '      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",\n'
        '      "title": "Concise summary of detected risk",\n'
        '      "description": "Specific details and evidence from database observations",\n'
        '      "delivery_impact": "Operational delivery impact on milestones or customer SLA",\n'
        '      "recommended_action": "Actionable corrective action or escalation"\n'
        '    }\n'
        '  ],\n'
        '  "answer": "Operational surveillance summary."\n'
        "}\n"
        "Respond ONLY with valid JSON."
    )

    try:
        from .domo_client import DomoTextLLM
        repair_llm = DomoTextLLM(max_tokens=2000, temperature=0.0)
        repair_raw = repair_llm.invoke(repair_prompt)
        from .agent_loop import _extract_json
        repair_dict = _extract_json(repair_raw)
        norm_repaired_risks = normalize_monitoring_decision_dict(repair_dict)
        repaired_validated = []
        for item in norm_repaired_risks:
            v_item = MonitoredRiskItem.model_validate(item)
            repaired_validated.append(v_item.model_dump())
        logger.info(f"Monitoring agent repair succeeded with {len(repaired_validated)} risks.")
        return repaired_validated, all_steps, "success"
    except Exception as rep_err:
        logger.warning(f"Monitoring agent repair attempt failed: {rep_err}")
        return None, all_steps, "validation_failed_twice"
