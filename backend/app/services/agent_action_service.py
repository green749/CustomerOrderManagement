import os
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ..config import settings
from ..models.auth import User
from ..models.business import FactCustomerOrder
from ..models.workflow import AgentAction, RiskAlert, OrderAssessment, CommitmentProposal
from ..repositories.agent_action_repo import AgentActionRepository
from ..repositories.commitment_repo import CommitmentRepository
from ..repositories.audit_repo import AuditRepository
from .email_service import EmailService

logger = logging.getLogger("manufacturing.services.agent_actions")


def utcnow():
    return datetime.now(timezone.utc)


class AgentActionService:
    """
    Agent 3 Corrective Action Service:
    - Proposes matching actions on risk detection.
    - Manages lifecycle (PROPOSED -> APPROVED -> EXECUTED / REJECTED / FAILED).
    - Dispatches notifications via EmailService.
    - Never mutates production / inventory source tables directly.
    - Handoff to FeasibilityService for REQUEST_REASSESSMENT revisions.
    """

    @classmethod
    def get_auto_execute_types(cls) -> set:
        raw = os.environ.get("AGENT3_AUTO_EXECUTE_ACTIONS", getattr(settings, "agent3_auto_execute_actions", ""))
        return {a.strip().upper() for a in raw.split(",") if a.strip()}

    @classmethod
    def get_max_actions_per_order(cls) -> int:
        raw = os.environ.get("AGENT3_MAX_ACTIONS_PER_ORDER")
        if raw is not None:
            try:
                return int(raw)
            except ValueError:
                pass
        return getattr(settings, "agent3_max_actions_per_order", 5)

    @classmethod
    def get_max_actions_per_day(cls) -> int:
        raw = os.environ.get("AGENT3_MAX_ACTIONS_PER_DAY")
        if raw is not None:
            try:
                return int(raw)
            except ValueError:
                pass
        return getattr(settings, "agent3_max_actions_per_day", 50)

    @classmethod
    def determine_action_type(
        cls,
        risk_category: str,
        severity: Optional[str] = None,
        delivery_impact: Optional[str] = None,
    ) -> str:
        cat = (risk_category or "").upper().strip()
        sev = (severity or "").upper().strip()
        impact = (delivery_impact or "").lower()

        # Any delay-related risk or risk with delivery impact and severity >= MEDIUM triggers REQUEST_REASSESSMENT
        delay_cats = {
            "DELIVERY_DATE_BREACHED",
            "CARRIER_TRANSIT_DELAY",
            "PRODUCTION_DELAY",
            "TRANSIT_BOTTLENECK",
            "SHIPMENT_EXCEPTION",
        }
        has_delivery_impact = any(k in impact for k in ["delay", "breach", "impact", "sla", "late", "behind", "rework", "shortage"])
        if (cat in delay_cats or has_delivery_impact) and sev in ("CRITICAL", "HIGH", "MEDIUM"):
            return "REQUEST_REASSESSMENT"

        if cat in ("DELIVERY_DATE_BREACHED", "CARRIER_TRANSIT_DELAY"):
            return "REQUEST_REASSESSMENT"
        elif cat in ("RAW_MATERIAL_SHORTAGE", "PRODUCTION_DELAY", "QUALITY_HOLD", "MES_CAPACITY_BOTTLENECK"):
            return "REQUEST_EXPEDITE"
        elif cat in ("SHIPMENT_EXCEPTION", "TRANSIT_BOTTLENECK"):
            return "REQUEST_CARRIER_UPGRADE"
        else:
            return "NOTIFY_CUSTOMER_REVISED_DATE"

    @classmethod
    def propose_action_for_risk(
        cls,
        db: Session,
        alert: RiskAlert,
        risk_dict: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentAction]:
        """
        Evaluate and propose a matching action for a newly recorded risk alert.
        Enforces:
        - Per-order and per-day caps
        - Duplicate suppression for identical open actions
        - Auto-execute evaluation against AGENT3_AUTO_EXECUTE_ACTIONS
        """
        order_id = alert.customer_order_id
        cat = alert.risk_category

        # 1. Check per-order cap
        max_order = cls.get_max_actions_per_order()
        current_order_actions = AgentActionRepository.count_open_actions_for_order(db, order_id)
        if current_order_actions >= max_order:
            logger.info(f"Skipping action for order {order_id}: reached per-order cap ({current_order_actions}/{max_order})")
            return None

        # 2. Check per-day cap & governor limits
        from .agent_controls_service import AgentControlsService
        if not AgentControlsService.check_and_enforce_auto_actions_limit(db, "agent3"):
            logger.warning(f"Skipping action for order {order_id}: daily auto-action governor limit reached.")
            return None

        max_day = cls.get_max_actions_per_day()
        today_actions = AgentActionRepository.count_daily_actions(db)
        if today_actions >= max_day:
            logger.warning(f"Skipping action for order {order_id}: reached per-day cap ({today_actions}/{max_day})")
            return None

        # 3. Determine matching action type
        action_type = cls.determine_action_type(cat, severity=alert.severity, delivery_impact=alert.delivery_impact)

        # 4. Skip proposing if an identical open action already exists
        existing_open = AgentActionRepository.find_existing_open_action(db, order_id, action_type)
        if existing_open:
            logger.info(f"Skipping action for order {order_id}: identical open action #{existing_open.id} ({action_type}) already exists")
            return existing_open

        # 5. Evaluate approval policy & Confidence level
        auto_types = cls.get_auto_execute_types()
        requires_approval = action_type not in auto_types

        confidence = (risk_dict or {}).get("confidence", "HIGH")
        if str(confidence).upper() == "LOW":
            # Requirement 1: Low confidence escalates to NEEDS_HUMAN, suppresses auto-execution
            requires_approval = True
            AgentControlsService.escalate_item(
                db=db,
                customer_order_id=order_id,
                reason=f"Agent 3 risk confidence is LOW for {cat} ({alert.title})",
                agent_name="agent3",
                details={"alert_id": alert.id, "risk": risk_dict, "action_type": action_type},
            )

        parameters = {
            "customer_order_id": order_id,
            "alert_id": alert.id,
            "risk_category": cat,
            "severity": alert.severity,
            "department": alert.department,
            "title": alert.title,
            "delivery_impact": alert.delivery_impact,
            "recommended_action": alert.recommended_action,
            "detected_risks": [risk_dict] if risk_dict else [{
                "department": alert.department,
                "risk_category": cat,
                "severity": alert.severity,
                "title": alert.title,
                "delivery_impact": alert.delivery_impact,
                "recommended_action": alert.recommended_action,
            }],
        }

        # 6. Create proposed action
        action = AgentActionRepository.create_action(
            db=db,
            alert_id=alert.id,
            customer_order_id=order_id,
            action_type=action_type,
            parameters=parameters,
            requires_approval=requires_approval,
            proposed_by="agent3-monitoring",
            status="PROPOSED",
        )

        AuditRepository.log(
            db=db,
            action="PROPOSE_ACTION",
            entity="agent_action",
            entity_id=str(action.id),
            payload={
                "action_type": action_type,
                "customer_order_id": order_id,
                "alert_id": alert.id,
                "requires_approval": requires_approval,
            },
        )

        # 7. Auto-execute if permitted
        if not requires_approval:
            logger.info(f"Action #{action.id} ({action_type}) permitted for auto-execution.")
            action = cls.execute_action(db, action.id)

        return action

    @classmethod
    def execute_action(
        cls,
        db: Session,
        action_id: int,
        user: Optional[User] = None,
    ) -> AgentAction:
        """
        Execute an approved or auto-execute allowed agent action.
        Writes to audit log and sends appropriate email notification via EmailService.
        Never modifies production / inventory source data directly.
        """
        action = AgentActionRepository.get_action_by_id(db, action_id)
        if not action:
            raise ValueError(f"Agent action #{action_id} not found.")

        if action.status == "EXECUTED":
            return action

        user_id = user.id if user else None
        order_id = action.customer_order_id
        action_type = action.action_type
        now = utcnow()

        try:
            if action_type == "REQUEST_EXPEDITE":
                dept = (action.parameters or {}).get("department", "MES")
                recipient, is_cfg = EmailService.get_recipient_for_department(db, dept)
                subject = f"[ACTION EXECUTED] Expedite Requested: Order {order_id}"
                body = (
                    f"Agent 3 Corrective Action #{action.id}: Production / Material Expedite Requested.\n\n"
                    f"Customer Order: {order_id}\n"
                    f"Target Department: {dept}\n"
                    f"Risk Details: {(action.parameters or {}).get('title', 'Schedule Delay Risk')}\n"
                    f"Recommended Action: {(action.parameters or {}).get('recommended_action', 'Prioritize parts assembly')}\n\n"
                    f"Authorized by: {user.full_name if user else 'Agent 3 Auto-Execution Policy'}\n"
                    f"Timestamp: {now.isoformat()}"
                )
                EmailService._dispatch_and_persist_notification(
                    db=db,
                    alert_id=action.alert_id,
                    customer_order_id=order_id,
                    recipient_email=recipient,
                    recipient_category="OPERATIONAL",
                    department=dept,
                    notification_type="ACTION_REQUIRED",
                    subject=subject,
                    body_text=body,
                )
                exec_result = {
                    "status": "SUCCESS",
                    "action_type": action_type,
                    "recipient": recipient,
                    "message": f"Expedite notification dispatched to {dept} ({recipient})",
                }

            elif action_type == "NOTIFY_CUSTOMER_REVISED_DATE":
                recipient, is_cfg = EmailService.get_customer_service_recipient(db)
                subject = f"[ACTION EXECUTED] Schedule Revision Notice: Order {order_id}"
                body = (
                    f"Agent 3 Corrective Action #{action.id}: Customer Service Delivery Schedule Revision.\n\n"
                    f"Customer Order: {order_id}\n"
                    f"Delivery Impact: {(action.parameters or {}).get('delivery_impact', 'Potential schedule variance')}\n"
                    f"Mitigation Directive: Notify customer account manager of schedule alignment.\n\n"
                    f"Authorized by: {user.full_name if user else 'Agent 3 Auto-Execution Policy'}\n"
                    f"Timestamp: {now.isoformat()}"
                )
                EmailService._dispatch_and_persist_notification(
                    db=db,
                    alert_id=action.alert_id,
                    customer_order_id=order_id,
                    recipient_email=recipient,
                    recipient_category="CUSTOMER_SERVICE",
                    department="CUSTOMER_SERVICE",
                    notification_type="DELIVERY_RISK",
                    subject=subject,
                    body_text=body,
                )
                exec_result = {
                    "status": "SUCCESS",
                    "action_type": action_type,
                    "recipient": recipient,
                    "message": f"Customer Service notification dispatched to {recipient}",
                }

            elif action_type == "REQUEST_CARRIER_UPGRADE":
                recipient, is_cfg = EmailService.get_recipient_for_department(db, "TMS")
                subject = f"[ACTION EXECUTED] Carrier Upgrade Requested: Order {order_id}"
                body = (
                    f"Agent 3 Corrective Action #{action.id}: Expedited Freight / Carrier Upgrade Requested.\n\n"
                    f"Customer Order: {order_id}\n"
                    f"Reason: {(action.parameters or {}).get('title', 'Transit milestone delay')}\n"
                    f"Directive: Transition shipment assignment to express air / premium dedicated carrier.\n\n"
                    f"Authorized by: {user.full_name if user else 'Agent 3 Auto-Execution Policy'}\n"
                    f"Timestamp: {now.isoformat()}"
                )
                EmailService._dispatch_and_persist_notification(
                    db=db,
                    alert_id=action.alert_id,
                    customer_order_id=order_id,
                    recipient_email=recipient,
                    recipient_category="OPERATIONAL",
                    department="TMS",
                    notification_type="ACTION_REQUIRED",
                    subject=subject,
                    body_text=body,
                )
                exec_result = {
                    "status": "SUCCESS",
                    "action_type": action_type,
                    "recipient": recipient,
                    "message": f"Carrier upgrade request dispatched to TMS ({recipient})",
                }

            elif action_type == "REQUEST_REASSESSMENT":
                # Requirement 4: Call FeasibilityService to reassess order with current state and create revised PENDING proposal (revision + 1)
                from .feasibility_service import FeasibilityService
                from .approval_policy_service import get_or_create_policy_engine_user
                from ..models.workflow import OrderMonitoringRecord

                order = db.query(FactCustomerOrder).filter(
                    FactCustomerOrder.customer_order_id == order_id
                ).first()
                if not order:
                    raise ValueError(f"Order '{order_id}' not found for reassessment handoff.")

                mon_rec = db.query(OrderMonitoringRecord).filter(
                    OrderMonitoringRecord.customer_order_id == order_id
                ).first()

                # Target delivery date MUST be customer's PROMISED date
                promised_date = None
                if mon_rec and mon_rec.approved_delivery_date:
                    promised_date = mon_rec.approved_delivery_date
                elif order.confirmed_delivery_date:
                    promised_date = order.confirmed_delivery_date
                else:
                    promised_date = order.requested_delivery_date or (date.today() + timedelta(days=20))

                max_rev = CommitmentRepository.get_max_revision(db, order_id)
                new_rev = max_rev + 1

                ref_date = settings.effective_reference_date or date.today()

                # Pass monitoring context (alert ID, detected risks)
                monitoring_ctx = {
                    "alert_id": action.alert_id,
                    "action_id": action.id,
                    "risks": (action.parameters or {}).get("detected_risks", []),
                    "promised_date": str(promised_date),
                }

                sys_user = user or get_or_create_policy_engine_user(db)
                assessment = FeasibilityService.assess_new_order(
                    db=db,
                    customer_id=order.customer_id,
                    product_id=order.product_id,
                    order_qty=order.order_qty,
                    requested_delivery_date=promised_date,
                    user=sys_user,
                    customer_order_id=order_id,
                    unit_price_inr=float(order.unit_price_inr or 15000.0),
                    priority=order.priority or "MEDIUM",
                    channel=order.channel or "EDI",
                    submit_for_approval=False,
                    as_of_date=ref_date,
                    monitoring_context=monitoring_ctx,
                )

                revised_date = assessment.estimated_delivery_date or (ref_date + timedelta(days=14))
                delay_days = (revised_date - promised_date).days if (revised_date and promised_date) else 0

                if delay_days <= 0:
                    verdict = "ON_TIME"
                elif delay_days > 0:
                    verdict = "DELAYED"
                else:
                    verdict = "AT_RISK"
                if delay_days == 0 and (assessment.blockers_summary or assessment.confidence_level == "LOW"):
                    verdict = "AT_RISK"

                assessment.revised_estimated_date = revised_date
                assessment.delay_days = delay_days
                assessment.verdict = verdict

                reasons = [
                    f"Agent 3 Reassessment handoff from Alert #{action.alert_id} ({action.action_type})",
                    f"Promised delivery date: {promised_date}. Recalculated achievable delivery date: {revised_date}.",
                    f"Delivery Verdict: {verdict} ({'+' if delay_days > 0 else ''}{delay_days} days variance).",
                ]
                if assessment.blockers_summary:
                    reasons.extend(assessment.blockers_summary[:2])

                # Create revised PENDING proposal with revision + 1
                revised_prop = CommitmentProposal(
                    customer_order_id=order_id,
                    proposed_date=revised_date,
                    recommended_by="agent3-monitoring",
                    reasons=reasons,
                    status="PENDING",
                    revised_estimated_date=revised_date,
                    delay_days=delay_days,
                    verdict=verdict,
                    created_by=sys_user.id,
                    revision=new_rev,
                    created_at=now,
                )
                db.add(revised_prop)
                db.commit()
                db.refresh(revised_prop)
                assessment.proposal_id = revised_prop.id
                db.commit()

                # Notify Customer Service about new revision waiting for commercial review
                cs_email, is_cfg = EmailService.get_customer_service_recipient(db)
                subject = f"[REASSESSMENT PENDING] Revised Proposal #{revised_prop.id} (Rev {new_rev}) for {order_id}"
                body = (
                    f"Agent 3 Reassessment Complete: Revised Commitment Proposal #{revised_prop.id} (Revision {new_rev}) is PENDING approval.\n\n"
                    f"Order ID: {order_id}\n"
                    f"Revised Achievable Date: {revised_date}\n"
                    f"Trigger Alert ID: {action.alert_id}\n"
                    f"Assessment Code: {assessment.assessment_id}\n\n"
                    f"Action Required: Customer Service approver must review and approve revision in Approvals Workspace to re-baseline delivery monitoring."
                )
                EmailService._dispatch_and_persist_notification(
                    db=db,
                    alert_id=action.alert_id,
                    customer_order_id=order_id,
                    recipient_email=cs_email,
                    recipient_category="CUSTOMER_SERVICE",
                    department="CUSTOMER_SERVICE",
                    notification_type="ACTION_REQUIRED",
                    subject=subject,
                    body_text=body,
                )

                exec_result = {
                    "status": "SUCCESS",
                    "action_type": action_type,
                    "revised_proposal_id": revised_prop.id,
                    "revision": new_rev,
                    "proposed_date": str(revised_date),
                    "assessment_id": assessment.assessment_id,
                    "message": f"Created revised PENDING proposal #{revised_prop.id} (Revision {new_rev}).",
                }
            else:
                exec_result = {
                    "status": "SUCCESS",
                    "action_type": action_type,
                    "message": f"Action {action_type} executed successfully.",
                }

            # Update action state
            action = AgentActionRepository.update_action_status(
                db=db,
                action=action,
                status="EXECUTED",
                approved_by=user_id or action.approved_by,
                executed_at=now,
                result=exec_result,
            )

            AuditRepository.log(
                db=db,
                action="EXECUTE_ACTION",
                entity="agent_action",
                entity_id=str(action.id),
                user_id=user_id,
                payload={
                    "action_id": action.id,
                    "action_type": action_type,
                    "customer_order_id": order_id,
                    "result": exec_result,
                },
            )
            return action

        except Exception as e:
            logger.error(f"Error executing agent action #{action.id}: {e}", exc_info=True)
            action = AgentActionRepository.update_action_status(
                db=db,
                action=action,
                status="FAILED",
                result={"status": "FAILED", "error": str(e)},
            )
            AuditRepository.log(
                db=db,
                action="ACTION_FAILED",
                entity="agent_action",
                entity_id=str(action.id),
                user_id=user_id,
                payload={"error": str(e)},
            )
            return action

    @classmethod
    def approve_action(cls, db: Session, action_id: int, user: User) -> AgentAction:
        action = AgentActionRepository.get_action_by_id(db, action_id)
        if not action:
            raise ValueError(f"Agent action #{action_id} not found.")

        if action.status not in ("PROPOSED", "REJECTED"):
            raise ValueError(f"Cannot approve action #{action_id} in status '{action.status}'.")

        action.status = "APPROVED"
        action.approved_by = user.id
        action.updated_at = utcnow()
        db.commit()

        AuditRepository.log(
            db=db,
            action="APPROVE_ACTION",
            entity="agent_action",
            entity_id=str(action.id),
            user_id=user.id,
            payload={"action_type": action.action_type, "customer_order_id": action.customer_order_id},
        )

        return cls.execute_action(db=db, action_id=action.id, user=user)

    @classmethod
    def reject_action(cls, db: Session, action_id: int, user: User, reason: Optional[str] = None) -> AgentAction:
        action = AgentActionRepository.get_action_by_id(db, action_id)
        if not action:
            raise ValueError(f"Agent action #{action_id} not found.")

        if action.status != "PROPOSED":
            raise ValueError(f"Cannot reject action #{action_id} in status '{action.status}'.")

        res_payload = {"rejected": True, "reason": reason or "Rejected by reviewer", "rejected_by": user.id}
        action = AgentActionRepository.update_action_status(
            db=db,
            action=action,
            status="REJECTED",
            approved_by=user.id,
            result=res_payload,
        )

        AuditRepository.log(
            db=db,
            action="REJECT_ACTION",
            entity="agent_action",
            entity_id=str(action.id),
            user_id=user.id,
            payload={"reason": reason},
        )
        return action
