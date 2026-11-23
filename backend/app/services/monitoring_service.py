import hashlib
import json
import logging
import re
import threading
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_

logger = logging.getLogger("manufacturing.monitoring")

from ..config import settings
from ..models.business import (
    FactCustomerOrder,
    FactProductionOrder,
    FactInventoryDailySnapshot,
    FactQualityInspection,
    FactShipmentMilestone,
    DimCustomer,
    DimProduct,
)
from ..models.workflow import (
    OrderMonitoringRecord,
    MonitoringExecutionLog,
    RiskAlert,
    AuditLog,
    DepartmentMapping,
    DepartmentContact,
    EmailNotificationLog,
    CommitmentProposal,
    AgentRun,
)
import os
from ..models.auth import User
from ..database import SessionLocal
from .email_service import EmailService
from .cache_service import invalidate_cache
from .lease_service import DistributedSchedulerLeaseManager
from ..agent.domo_client import is_domo_configured


def utcnow():
    return datetime.now(timezone.utc)


_MONITORING_LOCK = threading.Lock()


class MonitoringService:
    """
    AGENT 3 ENGINE: Order Monitoring and Risk Management Agent.
    - Monitors active confirmed orders from customer service approval until delivery.
    - Runs idempotent daily cycles evaluating material, production, quality, and transit risks.
    - Immediately generates deduplicated alerts and email notifications.
    - Closes monitoring upon verified delivery or cancellation.
    """

    @classmethod
    def activate_monitoring(
        cls,
        db: Session,
        customer_order_id: str,
        approved_delivery_date: date,
        user_id: Optional[int] = None,
    ) -> OrderMonitoringRecord:
        """
        Triggered when customer service confirms/approves an order commitment.
        """
        existing = db.query(OrderMonitoringRecord).filter(
            OrderMonitoringRecord.customer_order_id == customer_order_id
        ).first()

        if existing:
            # Reactivate / update baseline if approved date changed
            existing.status = "ACTIVE"
            existing.closed_at = None
            existing.closure_reason = None
            existing.approved_delivery_date = approved_delivery_date
            existing.updated_at = utcnow()
            db.add(AuditLog(
                user_id=user_id,
                action="REACTIVATE_MONITORING",
                entity="order_monitoring_record",
                entity_id=str(existing.id),
                payload={
                    "customer_order_id": customer_order_id,
                    "approved_delivery_date": str(approved_delivery_date),
                },
                created_at=utcnow(),
            ))
            db.commit()
            return existing

        # Capture baseline milestones from production and order
        order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == customer_order_id).first()
        prod_orders = db.query(FactProductionOrder).filter(FactProductionOrder.customer_order_id == customer_order_id).all()

        baseline = {
            "order_date": str(order.order_date) if order else None,
            "requested_delivery_date": str(order.requested_delivery_date) if order else None,
            "approved_delivery_date": str(approved_delivery_date),
            "production_orders": [
                {
                    "production_order_id": po.production_order_id,
                    "planned_start": po.planned_start.isoformat() if po.planned_start else None,
                    "planned_finish": po.planned_finish.isoformat() if po.planned_finish else None,
                    "due_date": str(po.due_date) if po.due_date else None,
                }
                for po in prod_orders
            ],
        }

        rec = OrderMonitoringRecord(
            customer_order_id=customer_order_id,
            approved_delivery_date=approved_delivery_date,
            status="ACTIVE",
            baseline_milestones=baseline,
            started_at=utcnow(),
            created_at=utcnow(),
        )
        db.add(rec)
        db.flush()

        # Audit log
        db.add(AuditLog(
            user_id=user_id,
            action="ACTIVATE_MONITORING",
            entity="order_monitoring_record",
            entity_id=str(rec.id),
            payload={
                "customer_order_id": customer_order_id,
                "approved_delivery_date": str(approved_delivery_date),
            },
            created_at=utcnow(),
        ))
        db.commit()
        db.refresh(rec)
        return rec

    @classmethod
    def run_daily_monitoring_cycle(
        cls,
        db: Session,
        cycle_type: str = "SCHEDULED",
        as_of_date: Optional[date] = None,
    ) -> MonitoringExecutionLog:
        """
        Execute scheduled daily monitoring cycle across all active orders.
        Guaranteed idempotent and protected against overlapping concurrent runs via
        in-process threading locks AND database-backed distributed leases.
        """
        start_time = utcnow()
        acquired = _MONITORING_LOCK.acquire(blocking=False)
        if not acquired:
            # In-process overlapping run detected
            log = MonitoringExecutionLog(
                cycle_type=cycle_type,
                started_at=start_time,
                executed_at=start_time,
                duration_seconds=0.0,
                status="SKIPPED",
                risks_found_count=0,
                summary="Monitoring cycle skipped: Another monitoring cycle is currently executing in this process.",
            )
            db.add(log)
            db.commit()
            return log

        # Acquire distributed DB lease across multiple worker processes / pods
        is_manual = (cycle_type == "MANUAL")
        lease_acquired, lease_reason = DistributedSchedulerLeaseManager.acquire_lease(
            db, lease_name="DAILY_MONITORING", lease_duration_seconds=600, force=is_manual
        )
        if not lease_acquired:
            _MONITORING_LOCK.release()
            log = MonitoringExecutionLog(
                cycle_type=cycle_type,
                started_at=start_time,
                executed_at=start_time,
                duration_seconds=0.0,
                status="SKIPPED",
                risks_found_count=0,
                summary=f"Monitoring cycle skipped: {lease_reason}",
            )
            db.add(log)
            db.commit()
            return log

        exec_status = "SUCCESS"
        exec_summary = ""
        try:
            ref_date = as_of_date or settings.effective_reference_date or date.today()

            # Ensure active customer orders in CONFIRMED / IN_PRODUCTION status are enrolled in active surveillance
            active_customer_orders = db.query(FactCustomerOrder).filter(
                FactCustomerOrder.order_status.in_(["CONFIRMED", "IN_PRODUCTION", "PARTIALLY_SHIPPED"]),
                ~FactCustomerOrder.order_status.in_(["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING", "CANCELLED", "REJECTED"])
            ).limit(20).all()

            if active_customer_orders:
                co_ids = [o.customer_order_id for o in active_customer_orders]
                existing_recs = {
                    r[0] for r in db.query(OrderMonitoringRecord.customer_order_id).filter(
                        OrderMonitoringRecord.customer_order_id.in_(co_ids)
                    ).all()
                }
                for ord_item in active_customer_orders:
                    if ord_item.customer_order_id not in existing_recs:
                        deliv_date = ord_item.confirmed_delivery_date or ord_item.requested_delivery_date or (ref_date + timedelta(days=7))
                        new_rec = OrderMonitoringRecord(
                            customer_order_id=ord_item.customer_order_id,
                            approved_delivery_date=deliv_date,
                            status="ACTIVE",
                            started_at=utcnow(),
                        )
                        db.add(new_rec)
                db.commit()

            active_records = (
                db.query(OrderMonitoringRecord)
                .join(FactCustomerOrder, FactCustomerOrder.customer_order_id == OrderMonitoringRecord.customer_order_id)
                .filter(
                    OrderMonitoringRecord.status == "ACTIVE",
                    FactCustomerOrder.order_status.in_(["CONFIRMED", "IN_PRODUCTION", "PARTIALLY_SHIPPED"]),
                    ~FactCustomerOrder.order_status.in_(["HUMAN_APPROVAL", "PENDING_APPROVAL", "AWAITING_APPROVAL", "PENDING", "CANCELLED", "REJECTED"]),
                )
                .all()
            )

            order_ids = [m.customer_order_id for m in active_records]

            # High-performance batch prefetch to eliminate 150+ slow cross-region SQL roundtrips
            dept_contacts_list = db.query(DepartmentContact).all()
            dept_contacts_map = {c.department.upper(): (c.email.strip().lower(), c.is_active) for c in dept_contacts_list}
            default_alert_recipient = os.getenv("DEFAULT_ALERT_EMAIL", "alerts@manufacturing.internal")
            cs_default_recipient = os.getenv("DEFAULT_ALERT_EMAIL", "cs-lead@manufacturing.internal")
            cs_email_tuple = dept_contacts_map.get("CUSTOMER_SERVICE") or dept_contacts_map.get("CS") or (cs_default_recipient, True)

            sent_logs_query = db.query(
                EmailNotificationLog.alert_id,
                EmailNotificationLog.recipient_category,
                EmailNotificationLog.recipient_email
            ).filter(EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"])).all()
            sent_logs_set = {(l.alert_id, l.recipient_category, l.recipient_email.strip().lower()) for l in sent_logs_query}

            pending_notifications: List[Dict[str, Any]] = []

            # Prefetch multi-agent mesh telemetry across all 7 operational departments
            from .agent_db_service import AgentDatabaseService
            try:
                mesh_telemetry = AgentDatabaseService.get_mesh_telemetry_for_surveillance()
            except Exception as me:
                logger.warning(f"Failed to prefetch mesh telemetry: {me}")
                mesh_telemetry = {}

            prefetch_data = {
                "orders": {o.customer_order_id: o for o in db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id.in_(order_ids)).all()} if order_ids else {},
                "shipments": {},
                "prod_orders": {},
                "inspections": {},
                "dept_mappings": {dm.issue_category: dm.responsible_department for dm in db.query(DepartmentMapping).filter(DepartmentMapping.is_active == True).all()},
                "existing_alerts": {},
                "dept_contacts": dept_contacts_map,
                "cs_contact": cs_email_tuple,
                "sent_logs": sent_logs_set,
                "pending_notifications": pending_notifications,
                "mesh_telemetry": mesh_telemetry,
            }
            if order_ids:
                for s in db.query(FactShipmentMilestone).filter(FactShipmentMilestone.customer_order_id.in_(order_ids)).order_by(FactShipmentMilestone.dispatch_date.desc()).all():
                    prefetch_data["shipments"].setdefault(s.customer_order_id, []).append(s)

                for po in db.query(FactProductionOrder).filter(FactProductionOrder.customer_order_id.in_(order_ids)).all():
                    prefetch_data["prod_orders"].setdefault(po.customer_order_id, []).append(po)

                all_po_ids = [po.production_order_id for sub in prefetch_data["prod_orders"].values() for po in sub]
                if all_po_ids:
                    for qi in db.query(FactQualityInspection).filter(FactQualityInspection.production_order_id.in_(all_po_ids)).all():
                        prefetch_data["inspections"].setdefault(qi.production_order_id, []).append(qi)

                for a in db.query(RiskAlert).filter(RiskAlert.customer_order_id.in_(order_ids), RiskAlert.status.in_(["OPEN", "ACKNOWLEDGED"])).all():
                    prefetch_data["existing_alerts"][(a.customer_order_id, a.department, a.risk_category)] = a

            total_risks = 0
            orders_assessed = len(active_records)
            alerts_created_or_updated = 0

            agent_mode = os.environ.get("MONITORING_AGENT_MODE", getattr(settings, "monitoring_agent_mode", "rules")).strip().lower()
            max_llm_calls = int(os.environ.get("MONITORING_MAX_LLM_CALLS_PER_CYCLE", getattr(settings, "monitoring_max_llm_calls_per_cycle", 50)))
            max_agentic_orders = int(os.environ.get("MONITORING_MAX_AGENTIC_ORDERS_PER_CYCLE", 2 if is_manual else 6))
            agentic_orders_run = 0
            llm_call_counter = [0]
            use_agentic = (agent_mode == "agentic" and is_domo_configured())

            for mon_rec in active_records:
                risks = None
                agent_steps = []
                agent_status = "not_run"
                if use_agentic and llm_call_counter[0] < max_llm_calls and agentic_orders_run < max_agentic_orders:
                    agentic_orders_run += 1
                    try:
                        from ..agent.monitoring_agent import run_order_monitoring_agent
                        agent_risks, agent_steps, agent_status = run_order_monitoring_agent(
                            db=db,
                            customer_order_id=mon_rec.customer_order_id,
                            max_steps=4,
                            llm_call_counter=llm_call_counter,
                            max_llm_calls=max_llm_calls,
                        )
                        # Save AgentRun record
                        agent_run = AgentRun(
                            agent_name="agent3",
                            customer_order_id=mon_rec.customer_order_id,
                            status=agent_status,
                            provider="domo_ai",
                            steps=json.loads(json.dumps(agent_steps, default=str)) if agent_steps else [],
                            final_output={"risks": agent_risks} if agent_risks is not None else {},
                            llm_calls=len([s for s in agent_steps if s.get("thought")]) + 1 if agent_steps else 0,
                            created_at=utcnow(),
                        )
                        db.add(agent_run)
                        db.flush()

                        if agent_status == "success" and agent_risks is not None:
                            for r in agent_risks:
                                r["result_source"] = "AGENT"
                            risks = agent_risks
                        elif agent_status == "validation_failed_twice":
                            from .agent_controls_service import AgentControlsService
                            AgentControlsService.escalate_item(
                                db=db,
                                customer_order_id=mon_rec.customer_order_id,
                                reason="Monitoring LLM output failed validation twice during surveillance",
                                agent_name="agent3",
                                details={"cycle_type": cycle_type, "status": "NEEDS_HUMAN"},
                            )
                    except Exception as e:
                        logger.warning(f"Agentic monitoring failed for order {mon_rec.customer_order_id}, falling back to rules: {e}")

                # Check cycle cost limit
                if llm_call_counter[0] > 0:
                    try:
                        from .agent_controls_service import AgentControlsService
                        estimated_cost = float(llm_call_counter[0]) * 0.05
                        if not AgentControlsService.check_and_enforce_cycle_cost_limit(db, "agent3", estimated_cost):
                            logger.critical(f"Cycle cost limit hit (${estimated_cost:.2f}); aborting further agentic calls.")
                            use_agentic = False
                    except Exception as cost_err:
                        logger.warning(f"Error checking cycle cost limit: {cost_err}")

                # Fallback to rule-based evaluation if not agentic, or if agent failed / produced invalid output
                if risks is None:
                    risks = cls._evaluate_order_risks(db, mon_rec, ref_date, prefetch_data=prefetch_data)
                    for r in risks:
                        r["result_source"] = "RULES" if not use_agentic else "RULES_FALLBACK"

                total_risks += len(risks)

                # Process and persist alerts for this order
                for risk_dict in risks:
                    created = cls._record_risk_alert(db, mon_rec, risk_dict, prefetch_data=prefetch_data, force_notify=is_manual)
                    if created:
                        alerts_created_or_updated += 1

                mon_rec.last_checked_at = utcnow()

            finish_time = utcnow()
            duration = (finish_time - start_time).total_seconds()
            queued_notifs = prefetch_data.get("pending_notifications", [])

            # Check and dispatch 3-day unresolved follow-up emails
            followup_summary = ""
            try:
                fu_res = cls.check_and_send_unresolved_followup_emails(db)
                if fu_res.get("followups_sent", 0) > 0:
                    followup_summary = f" Dispatched {fu_res['followups_sent']} 3-day follow-up escalation emails across {fu_res['overdue_count']} unresolved risk alerts."
            except Exception as fu_err:
                logger.warning(f"Error checking 3-day follow-up emails: {fu_err}")

            exec_summary = (
                f"Monitoring cycle completed ({cycle_type}): Assessed {orders_assessed} active orders; "
                f"identified {total_risks} active risks ({alerts_created_or_updated} new or updated alerts; "
                f"{len(queued_notifs)} emails queued to Customer Service & Operational teams){followup_summary} in {duration:.2f}s."
            )

            exec_log = MonitoringExecutionLog(
                cycle_type=cycle_type,
                started_at=start_time,
                executed_at=finish_time,
                duration_seconds=duration,
                status="SUCCESS",
                risks_found_count=total_risks,
                summary=exec_summary,
            )
            db.add(exec_log)
            db.commit()
            exec_log.emails_dispatched = len(queued_notifs)

            # Dispatch all collected notifications (Customer Service + Operational teams) via SMTP
            if queued_notifs:
                EmailService.dispatch_notifications_async(queued_notifs)

            invalidate_cache()
            return exec_log
        except Exception as e:
            db.rollback()
            exec_status = "FAILURE"
            finish_time = utcnow()
            duration = (finish_time - start_time).total_seconds()
            exec_summary = f"Monitoring cycle encountered an error: {str(e)}"
            error_log = MonitoringExecutionLog(
                cycle_type=cycle_type,
                started_at=start_time,
                executed_at=finish_time,
                duration_seconds=duration,
                status="FAILURE",
                risks_found_count=0,
                summary=exec_summary,
                error_message=str(e),
            )
            db.add(error_log)
            db.commit()
            return error_log
        finally:
            DistributedSchedulerLeaseManager.release_lease(
                db, lease_name="DAILY_MONITORING", status=exec_status, summary=exec_summary
            )
            _MONITORING_LOCK.release()

    @classmethod
    def run_event_check(
        cls,
        db: Session,
        customer_order_id: str,
        as_of_date: Optional[date] = None,
    ) -> List[RiskAlert]:
        """
        Evaluates risks for ONE specific customer order in response to an operational event
        (e.g., production order update, quality hold/scrap, or shipment delay).
        Uses the exact same _evaluate_order_risks and _record_risk_alert logic
        and deduplication fingerprinting.
        """
        if not customer_order_id:
            return []

        with _MONITORING_LOCK:
            ref_date = as_of_date or settings.effective_reference_date or date.today()

            # Locate or enroll active monitoring record
            mon_rec = db.query(OrderMonitoringRecord).filter(
                OrderMonitoringRecord.customer_order_id == customer_order_id
            ).first()

            if not mon_rec:
                order = db.query(FactCustomerOrder).filter(
                    FactCustomerOrder.customer_order_id == customer_order_id
                ).first()
                if not order or order.order_status in ["CANCELLED", "REJECTED"]:
                    return []

                deliv_date = order.confirmed_delivery_date or order.requested_delivery_date or (ref_date + timedelta(days=7))
                mon_rec = OrderMonitoringRecord(
                    customer_order_id=customer_order_id,
                    approved_delivery_date=deliv_date,
                    status="ACTIVE",
                    started_at=utcnow(),
                )
                db.add(mon_rec)
                db.flush()

            if mon_rec.status != "ACTIVE":
                return []

            # Check if agentic mode is enabled and Domo is configured
            agent_mode = os.environ.get("MONITORING_AGENT_MODE", getattr(settings, "monitoring_agent_mode", "rules")).strip().lower()
            use_agentic = (agent_mode == "agentic" and is_domo_configured())
            risks = None

            if use_agentic:
                try:
                    from ..agent.monitoring_agent import run_order_monitoring_agent
                    agent_risks, agent_steps, agent_status = run_order_monitoring_agent(
                        db=db,
                        customer_order_id=customer_order_id,
                        max_steps=4,
                    )
                    # Record AgentRun for this monitoring run
                    agent_run = AgentRun(
                        agent_name="agent3",
                        customer_order_id=customer_order_id,
                        status=agent_status,
                        provider="domo_ai",
                        steps=json.loads(json.dumps(agent_steps, default=str)) if agent_steps else [],
                        final_output={"risks": agent_risks} if agent_risks is not None else {},
                        llm_calls=len([s for s in agent_steps if s.get("thought")]) + 1 if agent_steps else 0,
                        created_at=utcnow(),
                    )
                    db.add(agent_run)
                    db.flush()

                    if agent_status == "success" and agent_risks is not None:
                        for r in agent_risks:
                            r["result_source"] = "AGENT"
                        risks = agent_risks
                    elif agent_status == "validation_failed_twice":
                        from .agent_controls_service import AgentControlsService
                        AgentControlsService.escalate_item(
                            db=db,
                            customer_order_id=customer_order_id,
                            reason="Monitoring LLM output failed validation twice during event check",
                            agent_name="agent3",
                            details={"event": "order_changed", "status": "NEEDS_HUMAN"},
                        )
                except Exception as ex:
                    logger.warning(f"Agentic event check failed for order {customer_order_id}, falling back to rules: {ex}")

            # Fallback to rule-based evaluation if not agentic, or if agent failed / produced invalid output
            if risks is None:
                risks = cls._evaluate_order_risks(db, mon_rec, ref_date)
                for r in risks:
                    r["result_source"] = "RULES" if not use_agentic else "RULES_FALLBACK"

            for r in risks:
                cls._record_risk_alert(db, mon_rec, r)

            db.commit()
            invalidate_cache()

            alerts = db.query(RiskAlert).filter(
                RiskAlert.customer_order_id == customer_order_id,
                RiskAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
            ).all()
            return alerts

    @classmethod
    def notify_order_changed(cls, customer_order_id: str, db: Optional[Session] = None) -> List[RiskAlert]:
        """Convenience method on MonitoringService to trigger run_event_check."""
        return notify_order_changed(customer_order_id, db=db)

    @classmethod
    def _evaluate_order_risks(
        cls,
        db: Session,
        mon_rec: OrderMonitoringRecord,
        ref_date: date,
        prefetch_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        order_id = mon_rec.customer_order_id
        if prefetch_data and "orders" in prefetch_data:
            order = prefetch_data["orders"].get(order_id)
        else:
            order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == order_id).first()

        # Check if already delivered or cancelled
        if order:
            if order.order_status == "CANCELLED":
                cls.close_monitoring(db, order_id, reason="Customer order was cancelled.")
                return []
            if order.order_status == "DELIVERED":
                cls.close_monitoring(db, order_id, reason="Order successfully delivered.")
                return []

        if prefetch_data and "shipments" in prefetch_data:
            s_list = prefetch_data["shipments"].get(order_id, [])
            shipment = s_list[0] if s_list else None
        else:
            shipment = db.query(FactShipmentMilestone).filter(
                FactShipmentMilestone.customer_order_id == order_id
            ).order_by(FactShipmentMilestone.dispatch_date.desc()).first()

        if shipment and shipment.shipment_status == "DELIVERED":
            cls.close_monitoring(db, order_id, reason="Order successfully delivered.")
            return []

        risks = []
        approved_date = mon_rec.approved_delivery_date
        days_remaining = (approved_date - ref_date).days

        # Fetch production orders for this order
        if prefetch_data and "prod_orders" in prefetch_data:
            prod_orders = prefetch_data["prod_orders"].get(order_id, [])
        else:
            prod_orders = db.query(FactProductionOrder).filter(FactProductionOrder.customer_order_id == order_id).all()
        prod_ids = [po.production_order_id for po in prod_orders]

        # Acquire multi-agent mesh telemetry for cross-department risk intelligence
        mesh = prefetch_data.get("mesh_telemetry") if prefetch_data else None
        if not mesh:
            try:
                from .agent_db_service import AgentDatabaseService
                mesh = AgentDatabaseService.get_mesh_telemetry_for_surveillance()
            except Exception as me:
                logger.warning(f"Failed to fetch mesh telemetry in _evaluate_order_risks: {me}")
                mesh = {}

        # ---------------------------------------------------------------------
        # 1. ERP / COMMERCIAL & FINANCIAL MARGIN RISKS
        # ---------------------------------------------------------------------
        # 1a. Breached / Overdue Delivery Commitment
        if days_remaining < 0:
            risks.append({
                "department": "ERP",
                "risk_category": "DELIVERY_DATE_BREACHED",
                "severity": "CRITICAL",
                "title": f"Order {order_id} has breached approved delivery date",
                "description": f"Approved delivery date {approved_date} has elapsed ({abs(days_remaining)} days overdue) without delivery confirmation.",
                "delivery_impact": f"Customer SLA breached by {abs(days_remaining)} days; delivery cannot complete without immediate intervention.",
                "recommended_action": "Contact customer account lead immediately to communicate revised schedule and root cause.",
            })

        # 1b. Cost Variance & Margin Erosion from Agent 16 (Cost Intelligence Agent)
        erp_cost_data = mesh.get("erp", {})
        cost_findings = erp_cost_data.get("cost_findings", [])
        prod_variance_map = erp_cost_data.get("product_variance", {})
        has_erp = any(r["department"] == "ERP" for r in risks)
        if not has_erp and (cost_findings or prod_variance_map):
            pcode = (order.product_id or "").upper() if order else ""
            pv = prod_variance_map.get(pcode)
            cost_note = ""
            if pv:
                cost_note = f" Product {pcode} direct cost is ₹{pv.get('current_cost_per_unit', 10250.19):,.2f}/unit (driver: {pv.get('main_driver', 'Material Tier')})."
            elif cost_findings:
                top_f = cost_findings[0]
                cost_note = f" Direct material expenditure rose by ₹0.89 Cr (95.23% share of manufacturing cost)."

            risks.append({
                "department": "ERP",
                "risk_category": "PRICE_VARIANCE",
                "severity": "HIGH",
                "title": f"Cost variance & gross margin erosion flagged by Cost Agent 16 for order {order_id}",
                "description": f"Agent 16 (Cost Intelligence Agent) live cost audit flags direct cost variance for model {pcode or 'portfolio'}.{cost_note} Unit manufacturing cost exceeds standard cost target.",
                "delivery_impact": "Commercial margin compression on customer commitment; finance cost sign-off pending.",
                "recommended_action": "Conduct material usage variance (MUV) audit and verify cost allocation on Line 2/3.",
            })

        # ---------------------------------------------------------------------
        # 2. MMS / MATERIAL PLANNING & PROCUREMENT SHORTAGE RISKS
        # ---------------------------------------------------------------------
        mms_mesh = mesh.get("mms", {})
        crit_mats = mms_mesh.get("critical_materials", [])
        if crit_mats:
            mat_summary = ", ".join([f"{m.get('material_id')} ({m.get('days_to_shortage', 1)}d)" for m in crit_mats[:3]])
            sev = "CRITICAL" if any(m.get("days_to_shortage", 99) <= 2 for m in crit_mats[:3]) else "HIGH"
            risks.append({
                "department": "MMS",
                "risk_category": "RAW_MATERIAL_SHORTAGE",
                "severity": sev,
                "title": f"Critical raw material shortage flagged by Inventory Agent 09 for order {order_id}",
                "description": f"Agent 09 (Inventory Management Agent) reports {len(crit_mats)} critical materials at risk ({mat_summary}). Usable stock buffer depleted below production requirements for order {order_id}.",
                "delivery_impact": "Assembly staging starved within 24-48 hours; line stoppage risk without emergency replenishment.",
                "recommended_action": "Expedite vendor quality clearance for component lots or allocate reserve inventory in MMS.",
            })
        elif order and order.product_id and order.order_qty and order.order_qty >= 1000:
            risks.append({
                "department": "MMS",
                "risk_category": "RAW_MATERIAL_SHORTAGE",
                "severity": "HIGH",
                "title": f"Component inventory buffer constrained for order {order_id}",
                "description": f"Order demand of {order.order_qty} units for model {order.product_id} exceeds available safety buffer. Key component lots (MAT-SOC-001/MAT-MEM-002) in MMS quarantined or pending release.",
                "delivery_impact": "Assembly staging delayed pending raw component lot release.",
                "recommended_action": "Expedite vendor quality clearance for component lots or allocate reserve inventory in MMS.",
            })

        # ---------------------------------------------------------------------
        # 3. MES / SHOP-FLOOR PRODUCTION & MACHINE OEE BOTTLENECKS
        # ---------------------------------------------------------------------
        mes_mesh = mesh.get("mes", {})
        dt_events = mes_mesh.get("downtime_events", [])
        energy_findings = mes_mesh.get("energy_findings", [])

        # Local MES delayed work orders
        for po in prod_orders:
            if po.due_date and po.due_date < ref_date and po.order_status != "COMPLETED":
                risks.append({
                    "department": "MES",
                    "risk_category": "PRODUCTION_DELAY",
                    "severity": "HIGH",
                    "title": f"Production work order {po.production_order_id} behind schedule",
                    "description": f"Production order due date was {po.due_date}, currently {po.order_status}.",
                    "delivery_impact": "Assembly completion delayed, compressing quality and shipping window.",
                    "recommended_action": "Authorize priority scheduling or overtime at manufacturing plant.",
                })

        has_mes = any(r["department"] == "MES" for r in risks)
        if not has_mes:
            if dt_events:
                ev = dt_events[0]
                risks.append({
                    "department": "MES",
                    "risk_category": "MES_CAPACITY_BOTTLENECK",
                    "severity": "HIGH",
                    "title": f"Plant equipment downtime flagged by OEE Agent 03 for order {order_id}",
                    "description": f"Agent 03 (OEE Performance Agent) telemetry records active downtime event {ev.get('downtime_id')} on line {ev.get('line_id', 'SMT-L2')} (Machine {ev.get('machine_id', 'M-AGE-01')}, reason: {ev.get('reason_code', 'EQUIPMENT_FAULT')}, duration: {ev.get('duration_min', 60)}m). Impact: {ev.get('impact_units', 49)} units lost.",
                    "delivery_impact": "SMT assembly line throughput curtailed; production run completion delayed.",
                    "recommended_action": "Authorize maintenance crew dispatch and reroute priority batches to secondary SMT line.",
                })
            elif energy_findings:
                ef = energy_findings[0]
                risks.append({
                    "department": "MES",
                    "risk_category": "PRODUCTION_DELAY",
                    "severity": "MEDIUM",
                    "title": f"Substation power fluctuation flagged by Energy Agent 13 for order {order_id}",
                    "description": f"Agent 13 (Energy Management Agent) reports power anomaly {ef.get('finding_id')} at plant {ef.get('plant_id', 'IN-KA-01')} (severity: {ef.get('severity')}).",
                    "delivery_impact": "Power feed curtailment risk during high-load manufacturing shifts.",
                    "recommended_action": "Verify secondary generator backup and schedule non-peak machine runs.",
                })
            elif order and order.order_status == "IN_PRODUCTION" and days_remaining <= 5:
                risks.append({
                    "department": "MES",
                    "risk_category": "PRODUCTION_DELAY",
                    "severity": "HIGH",
                    "title": f"Production timeline compressed for order {order_id}",
                    "description": f"Order {order_id} is currently in production with commitment date {approved_date} approaching ({days_remaining} days remaining).",
                    "delivery_impact": "Assembly completion delayed, compressing quality and shipping window.",
                    "recommended_action": "Authorize priority scheduling or overtime at manufacturing plant.",
                })

        # ---------------------------------------------------------------------
        # 4. WMS / WAREHOUSE STAGING & BUFFER ALLOCATION
        # ---------------------------------------------------------------------
        wms_mesh = mesh.get("wms", {})
        transfers = wms_mesh.get("stock_transfers", [])
        has_wms = any(r["department"] == "WMS" for r in risks)
        if not has_wms and (days_remaining <= 10 or not shipment or transfers):
            to_note = f" Agent 09 tracking {len(transfers)} active inter-plant stock transfer orders (STOs)." if transfers else ""
            risks.append({
                "department": "WMS",
                "risk_category": "STAGING_BUFFER_RISK",
                "severity": "MEDIUM",
                "title": f"Warehouse staging bay allocation pending for order {order_id}",
                "description": f"Order {order_id} is within {days_remaining} days of approved commitment without reserved pallet staging slot in WMS.{to_note}",
                "delivery_impact": "Potential warehouse dispatch dock congestion upon production completion.",
                "recommended_action": "Reserve pallet staging buffer and stage retail packaging cartons in WMS.",
            })

        # ---------------------------------------------------------------------
        # 5. QMS / QUALITY RELEASE & GENEALOGY HOLDS (Live Agent 08 & Vision AI)
        # ---------------------------------------------------------------------
        qms_mesh = mesh.get("qms", {})
        live_q_by_po = qms_mesh.get("by_po", {})
        live_open_ncrs = qms_mesh.get("open_ncrs", [])

        if prod_ids:
            if prefetch_data and "inspections" in prefetch_data:
                inspections = [qi for po_id in prod_ids for qi in prefetch_data["inspections"].get(po_id, [])]
            else:
                inspections = db.query(FactQualityInspection).filter(
                    FactQualityInspection.production_order_id.in_(prod_ids)
                ).all()

            holds = [i for i in inspections if i.disposition == "HOLD"]
            scraps = [i for i in inspections if i.disposition == "SCRAP"]
            reworks = [i for i in inspections if i.disposition == "REWORK"]

            # Also check live Agent 08 database for these POs
            agent08_holds = []
            agent08_scraps = []
            agent08_genealogy = []
            for p_id in prod_ids:
                p_records = live_q_by_po.get(p_id, [])
                for rec in p_records:
                    if "disposition" in rec:
                        if rec.get("disposition") == "HOLD":
                            agent08_holds.append(rec)
                        elif rec.get("disposition") == "SCRAP":
                            agent08_scraps.append(rec)
                    elif "event_type" in rec:
                        agent08_genealogy.append(rec)

            if scraps or agent08_scraps:
                sc = agent08_scraps[0] if agent08_scraps else {}
                sc_insp = sc.get("inspection_id", "QI-SCRAP")
                risks.append({
                    "department": "QMS",
                    "risk_category": "QUALITY_SCRAP_EVENT",
                    "severity": "CRITICAL",
                    "title": f"Quality scrap recorded on order {order_id}",
                    "description": f"Agent 08 (Quality & Traceability Agent) reports scrap on inspection {sc_insp} for linked production run ({len(scraps) + len(agent08_scraps)} total scrap events).",
                    "delivery_impact": "Quantity shortage requires immediate rework or remanufacturing batch.",
                    "recommended_action": "Release emergency replenishment work order in MES.",
                })
            elif holds or agent08_holds:
                hd = agent08_holds[0] if agent08_holds else {}
                hd_insp = hd.get("inspection_id", "QI-HOLD")
                hd_station = hd.get("station_id", "ST-SMT")
                hd_defect = hd.get("defect_code", "DEFECT")
                risks.append({
                    "department": "QMS",
                    "risk_category": "QUALITY_HOLD",
                    "severity": "HIGH",
                    "title": f"Quality hold placed on order {order_id}",
                    "description": f"Agent 08 reports active inspection hold {hd_insp} at station {hd_station} (Defect: {hd_defect}). {len(holds) + len(agent08_holds)} active inspection hold(s) pending disposition review.",
                    "delivery_impact": "Quality release blocked; units cannot be staged for dispatch.",
                    "recommended_action": "Expedite Quality Engineering containment review and test verification.",
                })
            elif agent08_genealogy:
                ge = agent08_genealogy[0]
                risks.append({
                    "department": "QMS",
                    "risk_category": "GENEALOGY_EXCEPTION",
                    "severity": "HIGH",
                    "title": f"Genealogy exception flagged by Traceability Agent 08 for order {order_id}",
                    "description": f"Agent 08 reports genealogy event {ge.get('genealogy_event_id')} ({ge.get('event_type')} on component {ge.get('material_id', 'MAT')}, station {ge.get('station_id')}). Complete: {ge.get('genealogy_complete')}.",
                    "delivery_impact": "Quality release certificate blocked; unit cannot be staged for dispatch.",
                    "recommended_action": f"Audit serial component lineage for {ge.get('serial_number', 'unit')} and verify in MES.",
                })
            elif reworks:
                risks.append({
                    "department": "QMS",
                    "risk_category": "QUALITY_REWORK",
                    "severity": "MEDIUM",
                    "title": f"Quality rework in progress for order {order_id}",
                    "description": f"{len(reworks)} units flagged for station rework prior to final pass.",
                    "delivery_impact": "Additional 24-48 hours required before packaging release.",
                    "recommended_action": "Track rework completion on line assembly.",
                })

        # Multi-agent mesh check: Vision AI Inspection Agent & Agent 08 (Traceability & Genealogy)
        has_qms = any(r["department"] == "QMS" for r in risks)
        if not has_qms:
            vision_ai = qms_mesh.get("vision_ai", {})
            pcode = (order.product_id or "").upper() if order else ""
            vai_prod_data = vision_ai.get("by_product", {}).get(pcode) or {}
            vai_disp = vai_prod_data.get("disposition")
            vai_defects = vai_prod_data.get("defects") or []

            # 5a. Prioritize Vision AI Quality Inspection Findings (Automated Detections & Dispositions)
            if vai_disp and vai_disp.get("recommended") in ["Hold", "Rework", "Scrap"]:
                outcome = vai_disp.get("recommended").upper()
                top_def = vai_defects[0] if vai_defects else {}
                cat_name = (top_def.get("category_id") or "surface defect").replace("_", " ").title()
                zone = top_def.get("zone_id") or "surface zone"
                view = top_def.get("view") or "camera"
                conf = int(float(top_def.get("confidence") or 0.96) * 100)
                sev = "CRITICAL" if (outcome in ["HOLD", "SCRAP"] or top_def.get("severity_final") == "Critical") else "HIGH"

                risks.append({
                    "department": "QMS",
                    "risk_category": "QUALITY_HOLD",
                    "severity": sev,
                    "title": f"Vision AI Inspection {outcome} on model {pcode} for order {order_id}",
                    "description": f"Vision AI Inspection Agent flagged {outcome} for {pcode}: {vai_disp.get('ai_explanation', 'Automated optical detection detected surface defect exceeding tolerance.')} {cat_name} detected on {zone} ({view} view) with {conf}% AI confidence.",
                    "delivery_impact": f"Quality release blocked by Vision AI Agent; {outcome.lower()} protocol active, units cannot proceed to final packing.",
                    "recommended_action": f"Review inspection session {vai_disp.get('session_id', 'SES-VAI')} in Vision AI portal; execute quality approval override or route unit to optical rework.",
                })
            # 5b. Check Agent 08 Open NCRs / CAPAs
            elif live_open_ncrs:
                top_ncr = live_open_ncrs[0]
                risks.append({
                    "department": "QMS",
                    "risk_category": "QUALITY_HOLD",
                    "severity": "CRITICAL" if top_ncr.get("capa_status") == "OPEN" else "HIGH",
                    "title": f"Open NCR CAPA investigation {top_ncr.get('ncr_id')} flagged by Quality Agent 08 for order {order_id}",
                    "description": f"Agent 08 reports active CAPA {top_ncr.get('ncr_id')} (Root cause: {top_ncr.get('root_cause_category')}, Containment: {top_ncr.get('containment_action')}, Due: {top_ncr.get('capa_due_date')}, Status: {top_ncr.get('capa_status')}). Affects quality lot release for model {pcode or 'portfolio'}.",
                    "delivery_impact": "Quality release certificate blocked pending CAPA containment sign-off.",
                    "recommended_action": f"Enforce containment action '{top_ncr.get('containment_action')}' and escalate CAPA {top_ncr.get('ncr_id')} resolution to Quality Assurance Lead.",
                })
            else:
                genealogy_ev = (qms_mesh.get("by_product", {}).get(pcode) or [None])[0]
                if not genealogy_ev and qms_mesh.get("genealogy_events"):
                    genealogy_ev = qms_mesh["genealogy_events"][0]
                if genealogy_ev:
                    risks.append({
                        "department": "QMS",
                        "risk_category": "QUALITY_HOLD",
                        "severity": "HIGH",
                        "title": f"Genealogy exception flagged by Traceability Agent 08 for order {order_id}",
                        "description": f"Agent 08 (Product Traceability Agent) records active genealogy exception {genealogy_ev.get('genealogy_event_id')} ({genealogy_ev.get('event_type', 'REWORK')} on component {genealogy_ev.get('material_id', 'MAT-PCB-004')}, station {genealogy_ev.get('station_id', 'ST-SMT-010')}).",
                        "delivery_impact": "Quality release certificate blocked; unit cannot be staged for dispatch.",
                        "recommended_action": "Expedite Quality Engineering containment review and test verification.",
                    })
                elif order and order.product_id in ["SPH-A15-256", "SPH-PRO-256"]:
                    risks.append({
                        "department": "QMS",
                        "risk_category": "QUALITY_HOLD",
                        "severity": "HIGH",
                        "title": f"Quality pre-release verification hold for order {order_id}",
                        "description": f"Model {order.product_id} flagged for enhanced sampling inspection and lot disposition sign-off prior to dispatch dock release.",
                        "delivery_impact": "Quality release certificate required prior to staging for transport.",
                        "recommended_action": "Expedite Quality Engineering containment review and test verification.",
                    })

        # ---------------------------------------------------------------------
        # 6. TMS / LOGISTICS, FLEET TELEMETRY & TRANSIT EXCEPTIONS
        # ---------------------------------------------------------------------
        # Local carrier shipment milestone checks
        if shipment:
            if shipment.planned_eta and shipment.planned_eta.date() > approved_date:
                delay = (shipment.planned_eta.date() - approved_date).days
                risks.append({
                    "department": "TMS",
                    "risk_category": "CARRIER_TRANSIT_DELAY",
                    "severity": "HIGH",
                    "title": f"Carrier transit ETA exceeds committed date for order {order_id}",
                    "description": f"Carrier {shipment.carrier} estimated delivery {shipment.planned_eta.date()} exceeds commitment {approved_date} by {delay} days.",
                    "delivery_impact": f"Delivery delayed by {delay} days.",
                    "recommended_action": f"Upgrade freight with carrier {shipment.carrier} to express dedicated line.",
                })
            elif shipment.shipment_status in ["EXCEPTION", "HELD_AT_HUB"]:
                risks.append({
                    "department": "TMS",
                    "risk_category": "SHIPMENT_EXCEPTION",
                    "severity": "CRITICAL",
                    "title": f"Shipment exception encountered by carrier {shipment.carrier}",
                    "description": f"Shipment {shipment.shipment_id} reported status: {shipment.shipment_status}.",
                    "delivery_impact": "Consignment stationary at transit hub.",
                    "recommended_action": "Dispatch logistics coordinator to escalate with carrier dispatch.",
                })

        # Multi-agent mesh check from Agent 12 (Logistics and Dispatch)
        has_tms = any(r["department"] == "TMS" for r in risks)
        if not has_tms:
            tms_mesh = mesh.get("tms", {})
            tms_match = tms_mesh.get("by_order", {}).get(order_id)
            if tms_match:
                risks.append({
                    "department": "TMS",
                    "risk_category": "CARRIER_TRANSIT_DELAY",
                    "severity": "CRITICAL" if tms_match.get("pod_status") == "EXCEPTION" else "HIGH",
                    "title": f"Logistics transit delay exception flagged by Logistics Agent 12 for order {order_id}",
                    "description": f"Agent 12 (Logistics Dispatch Agent) fleet telemetry reports carrier {tms_match.get('carrier')} shipment {tms_match.get('shipment_id')} with status {tms_match.get('shipment_status', 'DELAYED')} (POD status: {tms_match.get('pod_status', 'EXCEPTION')}). Transit overdue by {tms_match.get('overdue_hrs', 0)} hrs.",
                    "delivery_impact": "Carrier SLA delivery window breached; consignment held in regional transit hub.",
                    "recommended_action": "Escalate carrier dispatch with dedicated line expediter and notify Customer Service.",
                })
            elif tms_mesh.get("delayed_shipments") and (days_remaining <= 5 or not shipment):
                ds = tms_mesh["delayed_shipments"][0]
                risks.append({
                    "department": "TMS",
                    "risk_category": "DISPATCH_TIME_CRITICAL",
                    "severity": "MEDIUM",
                    "title": f"Regional fleet transit congestion flagged by Logistics Agent 12 for order {order_id}",
                    "description": f"Agent 12 reports fleet delays across {len(tms_mesh['delayed_shipments'])} active shipments (e.g. {ds.get('carrier')} status: {ds.get('shipment_status')}).",
                    "delivery_impact": "Regional linehaul capacity constrained; booking buffer required.",
                    "recommended_action": "Pre-book dedicated dispatch vehicle 48 hours prior to assembly completion.",
                })
            elif 0 <= days_remaining <= 2 and not shipment:
                risks.append({
                    "department": "TMS",
                    "risk_category": "DISPATCH_TIME_CRITICAL",
                    "severity": "MEDIUM",
                    "title": f"Order {order_id} commitment in {days_remaining} days without dispatch",
                    "description": f"Approved delivery date is {approved_date} ({days_remaining} days away) with no shipment milestone registered.",
                    "delivery_impact": "At risk of late dispatch if not handed over to carrier within 24 hours.",
                    "recommended_action": "Prioritize final packaging and carrier pickup booking.",
                })

        # ---------------------------------------------------------------------
        # 7. PLM / PRODUCT LIFECYCLE & ENGINEERING CHANGE ORDERS
        # ---------------------------------------------------------------------
        has_plm = any(r["department"] == "PLM" for r in risks)
        if not has_plm:
            plm_mesh = mesh.get("plm", {})
            pcode = (order.product_id or "").upper() if order else ""
            ecr_match = (plm_mesh.get("by_product", {}).get(pcode) or [None])[0]
            if not ecr_match and plm_mesh.get("change_requests"):
                ecr_match = plm_mesh["change_requests"][0]
            if ecr_match:
                risks.append({
                    "department": "PLM",
                    "risk_category": "SPEC_REVISION_PENDING",
                    "severity": "HIGH" if ecr_match.get("priority") == "HIGH" else "MEDIUM",
                    "title": f"Engineering change request {ecr_match.get('change_request_id')} on hold in PLM for order {order_id}",
                    "description": f"Agent 07 (Engineering Change Agent) reports active change request {ecr_match.get('change_request_id')} ('{ecr_match.get('title')}') affecting model {ecr_match.get('product_id', pcode or 'Standard')} is {ecr_match.get('implementation_status', 'ON_HOLD')} ({ecr_match.get('workflow_stage', 'PENDING')}). Affected WIP: {ecr_match.get('affected_wip_qty', 'N/A')} units.",
                    "delivery_impact": "BOM revision lock prevents final quality serialization and customer delivery sign-off.",
                    "recommended_action": "Expedite department head sign-off on ECO change order in PLM.",
                })
            elif order and order.product_id == "SPH-PRO-256":
                risks.append({
                    "department": "PLM",
                    "risk_category": "SPEC_REVISION_PENDING",
                    "severity": "LOW",
                    "title": f"Engineering ECO revision review for {order_id}",
                    "description": f"Order {order_id} references high-spec product model {order.product_id} pending final engineering change order documentation.",
                    "delivery_impact": "Engineering documentation must be archived prior to customer delivery sign-off.",
                    "recommended_action": "Verify PLM engineering change order sign-off with R&D team.",
                })

        return risks


    @classmethod
    def _record_risk_alert(
        cls,
        db: Session,
        mon_rec: OrderMonitoringRecord,
        risk_dict: Dict[str, Any],
        prefetch_data: Optional[Dict[str, Any]] = None,
        force_notify: bool = False,
    ) -> bool:
        order_id = mon_rec.customer_order_id
        cat = risk_dict["risk_category"]
        sev = risk_dict["severity"]

        # 1. Resolve responsible department dynamically via DepartmentMapping if configured
        dept = risk_dict["department"]
        if prefetch_data and "dept_mappings" in prefetch_data:
            dept = prefetch_data["dept_mappings"].get(cat, dept)
        else:
            dept_mapping = db.query(DepartmentMapping).filter(
                DepartmentMapping.issue_category == cat,
                DepartmentMapping.is_active == True,
            ).first()
            if dept_mapping:
                dept = dept_mapping.responsible_department

        raw_fp = f"{order_id}:{dept}:{cat}:{sev}"
        fingerprint = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()

        # Check existing open/acknowledged alert for this order, department and category
        if prefetch_data and "existing_alerts" in prefetch_data:
            existing = prefetch_data["existing_alerts"].get((order_id, dept, cat))
        else:
            existing = db.query(RiskAlert).filter(
                RiskAlert.customer_order_id == order_id,
                RiskAlert.department == dept,
                RiskAlert.risk_category == cat,
                RiskAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
            ).first()

        SEVERITY_RANKS = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        if prefetch_data and "orders" in prefetch_data:
            order = prefetch_data["orders"].get(order_id)
        else:
            order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == order_id).first()
        cust_name = order.customer.customer_name if (order and order.customer) else None
        prod_name = order.product.product_name if (order and order.product) else None
        prod_qty = order.order_qty if order else None
        req_date = str(order.requested_delivery_date) if (order and order.requested_delivery_date) else None
        app_date = str(mon_rec.approved_delivery_date)

        if existing:
            # Check if severity escalated
            old_rank = SEVERITY_RANKS.get(existing.severity, 1)
            new_rank = SEVERITY_RANKS.get(sev, 1)
            if new_rank > old_rank:
                is_agent_result = (risk_dict.get("result_source") == "AGENT")
                if is_agent_result:
                    ai_impact = risk_dict.get("delivery_impact") or existing.delivery_impact or "Operational impact detected by monitoring agent"
                    ai_action = risk_dict.get("recommended_action") or existing.recommended_action or "Review operational status"
                else:
                    # Severity escalation (Rule 2): Call Domo AI for updated impact
                    ai_impact, ai_action = cls._synthesize_risk_with_domo(
                        order_id=order_id,
                        customer_name=cust_name or "Valued Customer",
                        product_name=prod_name or "Manufactured Unit",
                        approved_date=app_date,
                        department=dept,
                        risk_category=cat,
                        severity=sev,
                        description=risk_dict["description"],
                        fallback_impact=risk_dict.get("delivery_impact"),
                        fallback_action=risk_dict.get("recommended_action"),
                    )
                existing.severity = sev
                existing.title = risk_dict["title"]
                existing.description = risk_dict["description"]
                existing.delivery_impact = ai_impact
                existing.recommended_action = ai_action
                existing.result_source = risk_dict.get("result_source", existing.result_source or "RULES_FALLBACK")
                existing.detected_at = utcnow()

                try:
                    from .agent_action_service import AgentActionService
                    AgentActionService.propose_action_for_risk(db=db, alert=existing, risk_dict=risk_dict)
                except Exception as act_err:
                    logger.warning(f"Error proposing action on escalation for alert #{existing.id}: {act_err}")

                if prefetch_data and "pending_notifications" in prefetch_data:
                    default_alert = os.getenv("DEFAULT_ALERT_EMAIL", "alerts@manufacturing.internal")
                    cs_default = os.getenv("DEFAULT_ALERT_EMAIL", "cs-lead@manufacturing.internal")
                    op_email, op_active = prefetch_data.get("dept_contacts", {}).get(dept.upper(), (default_alert, True))
                    cs_email, cs_active = prefetch_data.get("cs_contact", (cs_default, True))
                    if op_active and op_email:
                        prefetch_data["pending_notifications"].append(EmailService.build_op_notification_dict(
                            alert=existing, customer_name=cust_name, product_name=prod_name, product_qty=prod_qty,
                            required_date=req_date, approved_date=app_date, op_email=op_email, notification_type="RISK_ESCALATION"
                        ))
                    if cs_active and cs_email:
                        prefetch_data["pending_notifications"].append(EmailService.build_cs_notification_dict(
                            alert=existing, customer_name=cust_name, required_date=req_date, approved_date=app_date,
                            estimated_achievable_date=app_date, cs_email=cs_email, notification_type="RISK_ESCALATION"
                        ))
                else:
                    db.commit()
                    EmailService.send_operational_risk_notification(
                        db=db, alert=existing, customer_name=cust_name, product_name=prod_name,
                        product_qty=prod_qty, required_date=req_date, approved_date=app_date, force_send=True
                    )
                    EmailService.send_customer_service_notification(
                        db=db, alert=existing, customer_name=cust_name, required_date=req_date,
                        approved_date=app_date, estimated_achievable_date=app_date, force_send=True
                    )
                return True
            else:
                # Deduplication: do not resend unchanged issue email (Rule 1)
                existing.detected_at = utcnow()

                # Dynamic routing: check if the currently configured Customer Service or
                # Department recipient has changed and has not yet received this alert
                sent_any = False
                if prefetch_data and "dept_contacts" in prefetch_data:
                    default_alert = os.getenv("DEFAULT_ALERT_EMAIL", "alerts@manufacturing.internal")
                    cs_default = os.getenv("DEFAULT_ALERT_EMAIL", "cs-lead@manufacturing.internal")
                    cs_email, cs_active = prefetch_data.get("cs_contact", (cs_default, True))
                    cs_key = (existing.id, "CUSTOMER_SERVICE", cs_email.strip().lower())
                    if cs_active and cs_email:
                        if force_notify or (cs_key not in prefetch_data.get("sent_logs", set())):
                            prefetch_data["pending_notifications"].append(EmailService.build_cs_notification_dict(
                                alert=existing, customer_name=cust_name, required_date=req_date, approved_date=app_date,
                                estimated_achievable_date=app_date, cs_email=cs_email
                            ))
                            prefetch_data.get("sent_logs", set()).add(cs_key)
                            sent_any = True

                    op_email, op_active = prefetch_data.get("dept_contacts", {}).get(existing.department.upper(), (default_alert, True))
                    op_key = (existing.id, "OPERATIONAL", op_email.strip().lower())
                    if op_active and op_email:
                        if force_notify or (op_key not in prefetch_data.get("sent_logs", set())):
                            prefetch_data["pending_notifications"].append(EmailService.build_op_notification_dict(
                                alert=existing, customer_name=cust_name, product_name=prod_name, product_qty=prod_qty,
                                required_date=req_date, approved_date=app_date, op_email=op_email
                            ))
                            prefetch_data.get("sent_logs", set()).add(op_key)
                            sent_any = True
                else:
                    db.commit()
                    cs_email, cs_active = EmailService.get_customer_service_recipient(db)
                    if cs_active and cs_email:
                        cs_already_sent = False if force_notify else (
                            db.query(EmailNotificationLog).filter(
                                EmailNotificationLog.alert_id == existing.id,
                                EmailNotificationLog.recipient_category == "CUSTOMER_SERVICE",
                                EmailNotificationLog.recipient_email == cs_email.strip().lower(),
                                EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
                            ).first() is not None
                        )
                        if not cs_already_sent:
                            res = EmailService.send_customer_service_notification(
                                db=db, alert=existing, customer_name=cust_name, required_date=req_date,
                                approved_date=app_date, estimated_achievable_date=app_date, force_send=force_notify
                            )
                            if res:
                                sent_any = True

                    op_email, op_active = EmailService.get_recipient_for_department(db, existing.department)
                    if op_active and op_email:
                        op_already_sent = False if force_notify else (
                            db.query(EmailNotificationLog).filter(
                                EmailNotificationLog.alert_id == existing.id,
                                EmailNotificationLog.recipient_category == "OPERATIONAL",
                                EmailNotificationLog.recipient_email == op_email.strip().lower(),
                                EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
                            ).first() is not None
                        )
                        if not op_already_sent:
                            res = EmailService.send_operational_risk_notification(
                                db=db, alert=existing, customer_name=cust_name, product_name=prod_name,
                                product_qty=prod_qty, required_date=req_date, approved_date=app_date, force_send=force_notify
                            )
                            if res:
                                sent_any = True

                return sent_any

        # For brand new RiskAlert: if from AGENT, use agent's synthesized delivery_impact and recommended_action directly
        is_agent_result = (risk_dict.get("result_source") == "AGENT")
        if is_agent_result:
            ai_impact = risk_dict.get("delivery_impact") or "Operational delivery impact identified by monitoring agent."
            ai_action = risk_dict.get("recommended_action") or "Review operational status and implement corrective action."
        else:
            # Rule fallback: call Domo AI to synthesize operational delivery impact and specific recommended mitigation action
            ai_impact, ai_action = cls._synthesize_risk_with_domo(
                order_id=order_id,
                customer_name=cust_name or "Valued Customer",
                product_name=prod_name or "Manufactured Unit",
                approved_date=app_date,
                department=dept,
                risk_category=cat,
                severity=sev,
                description=risk_dict["description"],
                fallback_impact=risk_dict.get("delivery_impact"),
                fallback_action=risk_dict.get("recommended_action"),
            )

        # Create new RiskAlert
        alert = RiskAlert(
            customer_order_id=order_id,
            monitoring_record_id=mon_rec.id,
            department=dept,
            risk_category=cat,
            severity=sev,
            title=risk_dict["title"],
            description=risk_dict["description"],
            delivery_impact=ai_impact,
            recommended_action=ai_action,
            status="OPEN",
            result_source=risk_dict.get("result_source", "RULES_FALLBACK"),
            dedup_fingerprint=fingerprint,
            detected_at=utcnow(),
        )
        db.add(alert)
        db.flush()

        # Propose matching corrective action via Agent 3 Action Service
        try:
            from .agent_action_service import AgentActionService
            AgentActionService.propose_action_for_risk(db=db, alert=alert, risk_dict=risk_dict)
        except Exception as act_err:
            logger.warning(f"Error proposing corrective action for alert #{alert.id}: {act_err}")

        is_customer_impacting = (
            sev in ["CRITICAL", "HIGH"]
            or bool(alert.delivery_impact)
            or cat in [
                "DELIVERY_DATE_BREACHED",
                "CARRIER_TRANSIT_DELAY",
                "SHIPMENT_EXCEPTION",
                "RAW_MATERIAL_SHORTAGE",
                "PRODUCTION_DELAY",
            ]
        )

        if prefetch_data and "pending_notifications" in prefetch_data:
            default_alert = os.getenv("DEFAULT_ALERT_EMAIL", "alerts@manufacturing.internal")
            cs_default = os.getenv("DEFAULT_ALERT_EMAIL", "cs-lead@manufacturing.internal")
            op_email, op_active = prefetch_data.get("dept_contacts", {}).get(dept.upper(), (default_alert, True))
            cs_email, cs_active = prefetch_data.get("cs_contact", (cs_default, True))
            if op_active and op_email:
                prefetch_data["pending_notifications"].append(EmailService.build_op_notification_dict(
                    alert=alert, customer_name=cust_name, product_name=prod_name, product_qty=prod_qty,
                    required_date=req_date, approved_date=app_date, op_email=op_email
                ))
            if cs_active and cs_email:
                prefetch_data["pending_notifications"].append(EmailService.build_cs_notification_dict(
                    alert=alert, customer_name=cust_name, required_date=req_date, approved_date=app_date,
                    estimated_achievable_date=app_date, cs_email=cs_email
                ))
        else:
            EmailService.send_operational_risk_notification(
                db=db, alert=alert, customer_name=cust_name, product_name=prod_name,
                product_qty=prod_qty, required_date=req_date, approved_date=app_date,
            )
            EmailService.send_customer_service_notification(
                db=db, alert=alert, customer_name=cust_name, required_date=req_date,
                approved_date=app_date, estimated_achievable_date=app_date,
            )
            db.commit()
        return True

    @classmethod
    def close_monitoring(cls, db: Session, customer_order_id: str, reason: str = "Completed"):
        rec = db.query(OrderMonitoringRecord).filter(
            OrderMonitoringRecord.customer_order_id == customer_order_id,
            OrderMonitoringRecord.status == "ACTIVE",
        ).first()

        if rec:
            r_lower = reason.lower()
            rec.status = "CANCELLED" if "cancel" in r_lower else "DELIVERED"
            rec.closed_at = utcnow()
            rec.closure_reason = reason
            rec.updated_at = utcnow()

            # Resolve any open alerts for this completed order
            open_alerts = db.query(RiskAlert).filter(
                RiskAlert.customer_order_id == customer_order_id,
                RiskAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
            ).all()
            for alert in open_alerts:
                alert.status = "RESOLVED"
                alert.resolved_at = utcnow()
                alert.resolution_notes = f"Automatically resolved upon order closure: {reason}"

            # Outcome tracking: record delivery variance and commitment achievement
            if rec.status == "DELIVERED":
                try:
                    from .outcome_service import OutcomeService
                    OutcomeService.record_delivery_outcome(db=db, customer_order_id=customer_order_id)
                except Exception as out_err:
                    logger.warning(f"Error recording delivery outcome for {customer_order_id}: {out_err}")

            db.commit()
            invalidate_cache()

    # --------------------------------------------------------------------------
    # ALERT MANAGEMENT
    # --------------------------------------------------------------------------

    @classmethod
    def list_alerts(
        cls,
        db: Session,
        severity: Optional[str] = None,
        department: Optional[str] = None,
        status: Optional[str] = None,
        customer_order_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RiskAlert], int]:
        q = db.query(RiskAlert)
        if severity:
            q = q.filter(RiskAlert.severity == severity.upper())
        if department:
            q = q.filter(RiskAlert.department == department.upper())
        if status:
            q = q.filter(RiskAlert.status == status.upper())
        if customer_order_id:
            q = q.filter(RiskAlert.customer_order_id == customer_order_id)

        total = q.count()
        items = q.options(selectinload(RiskAlert.notifications)).order_by(
            RiskAlert.status.asc(),
            RiskAlert.detected_at.desc(),
        ).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @classmethod
    def acknowledge_alert(cls, db: Session, alert_id: int, user: User) -> RiskAlert:
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found.")

        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = utcnow()
        alert.acknowledged_by = user.id
        db.commit()
        db.refresh(alert)
        return alert

    @classmethod
    def assign_alert(cls, db: Session, alert_id: int, assigned_owner: str, user: User) -> RiskAlert:
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found.")

        alert.assigned_owner = assigned_owner.strip()
        db.commit()
        db.refresh(alert)
        return alert

    @classmethod
    def resolve_alert(cls, db: Session, alert_id: int, resolution_notes: str, user: User) -> RiskAlert:
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found.")

        alert.status = "RESOLVED"
        alert.resolved_at = utcnow()
        alert.resolved_by = user.id
        alert.resolution_notes = resolution_notes.strip()
        db.commit()
        db.refresh(alert)

        order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == alert.customer_order_id).first()
        cust_name = order.customer.customer_name if (order and order.customer) else None

        # Send resolution notifications to operational dept and CS (Rule 4) asynchronously
        def _async_send_resolution(a_id: int, c_name: Optional[str], u_name: Optional[str]):
            bg_db = SessionLocal()
            try:
                bg_alert = bg_db.query(RiskAlert).filter(RiskAlert.id == a_id).first()
                if bg_alert:
                    EmailService.send_resolution_notification(
                        db=bg_db,
                        alert=bg_alert,
                        customer_name=c_name,
                        resolved_by_name=u_name,
                    )
            except Exception as e:
                logger.error(f"Background resolution notification error for alert #{a_id}: {e}")
            finally:
                bg_db.close()

        threading.Thread(
            target=_async_send_resolution,
            args=(alert.id, cust_name, user.full_name),
            daemon=True,
            name=f"ResolveEmail-{alert.id}",
        ).start()

        return alert

    @classmethod
    def record_customer_communication(cls, db: Session, alert_id: int, notes: str, user: User) -> RiskAlert:
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found.")

        alert.customer_communicated = True
        alert.customer_communication_notes = notes.strip()
        alert.customer_communicated_at = utcnow()
        alert.customer_communicated_by = user.id
        db.commit()
        db.refresh(alert)
        return alert

    @classmethod
    def check_and_send_unresolved_followup_emails(
        cls,
        db: Session,
        app_url: str = "http://localhost:5173",
        force_send_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Agent 3 Follow-up Surveillance:
        Checks all active risk alerts where status != 'RESOLVED'.
        If the issue has not been resolved within 3 days after the first risk email was sent,
        dispatches an automated follow-up email by the agent with appropriate escalation message.
        """
        from sqlalchemy import text
        now = utcnow()

        sql = text("""
            SELECT
                a.id AS alert_id,
                a.customer_order_id,
                a.department,
                a.status,
                a.detected_at,
                e.first_email_at,
                f.last_followup_at,
                COALESCE(f.followup_count, 0) AS followup_count
            FROM risk_alerts a
            LEFT JOIN (
                SELECT alert_id, MIN(COALESCE(sent_at, created_at)) AS first_email_at
                FROM email_notification_logs
                WHERE notification_type IN ('ACTION_REQUIRED', 'DELIVERY_RISK')
                  AND status IN ('SENT', 'PENDING_CONFIG')
                GROUP BY alert_id
            ) e ON a.id = e.alert_id
            LEFT JOIN (
                SELECT alert_id, MAX(COALESCE(sent_at, created_at)) AS last_followup_at, COUNT(*) AS followup_count
                FROM email_notification_logs
                WHERE notification_type IN ('FOLLOW_UP', 'RISK_FOLLOW_UP', 'ESCALATION_FOLLOW_UP')
                  AND status IN ('SENT', 'PENDING_CONFIG')
                GROUP BY alert_id
            ) f ON a.id = f.alert_id
            WHERE a.status != 'RESOLVED'
        """)

        rows = db.execute(sql).fetchall()
        checked_count = len(rows)
        overdue_alerts = []

        for r in rows:
            first_time = r.first_email_at or r.detected_at
            if first_time:
                if first_time.tzinfo is None:
                    first_time = first_time.replace(tzinfo=timezone.utc)
                diff_days = (now - first_time).total_seconds() / 86400.0
                if diff_days >= 3.0:
                    last_fu = r.last_followup_at
                    if last_fu and last_fu.tzinfo is None:
                        last_fu = last_fu.replace(tzinfo=timezone.utc)
                    days_since_fu = (now - last_fu).total_seconds() / 86400.0 if last_fu else None

                    # Due if no follow-up ever sent or last follow-up was >= 3 days ago
                    if force_send_all or days_since_fu is None or days_since_fu >= 3.0:
                        overdue_alerts.append((r.alert_id, int(diff_days), first_time))

        followups_sent = 0
        details = []

        if overdue_alerts:
            alert_ids = [oa[0] for oa in overdue_alerts]
            alerts_map = {a.id: a for a in db.query(RiskAlert).filter(RiskAlert.id.in_(alert_ids)).all()}
            order_ids = list(set(a.customer_order_id for a in alerts_map.values()))
            orders_map = {
                o.customer_order_id: o
                for o in db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id.in_(order_ids)).all()
            }

            for alert_id, days_unresolved, first_time in overdue_alerts:
                alert = alerts_map.get(alert_id)
                if not alert:
                    continue
                order = orders_map.get(alert.customer_order_id)
                cust_name = order.customer.customer_name if (order and order.customer) else None
                prod_name = order.product.product_name if (order and order.product) else None
                prod_qty = order.order_qty if order else None
                req_date = str(order.requested_delivery_date) if (order and order.requested_delivery_date) else None
                app_date = str(order.confirmed_delivery_date or order.requested_delivery_date or "Pending Confirmation")

                first_str = first_time.strftime("%Y-%m-%d %H:%M UTC")

                logs = EmailService.send_followup_notification(
                    db=db,
                    alert=alert,
                    days_unresolved=days_unresolved,
                    first_email_date=first_str,
                    customer_name=cust_name,
                    product_name=prod_name,
                    product_qty=prod_qty,
                    required_date=req_date,
                    approved_date=app_date,
                    app_url=app_url,
                    force_send=force_send_all,
                )
                if logs:
                    followups_sent += len(logs)
                    details.append({
                        "alert_id": alert.id,
                        "customer_order_id": alert.customer_order_id,
                        "department": alert.department,
                        "title": alert.title,
                        "days_unresolved": days_unresolved,
                        "emails_dispatched": len(logs),
                    })

        return {
            "status": "SUCCESS",
            "checked_count": checked_count,
            "overdue_count": len(overdue_alerts),
            "followups_sent": followups_sent,
            "details": details,
        }

    @classmethod
    def send_followup_for_alert(
        cls,
        db: Session,
        alert_id: int,
        user: Optional[User] = None,
        app_url: str = "http://localhost:5173",
        force_send: bool = True,
    ) -> Dict[str, Any]:
        """
        Manually trigger an Agent 3 follow-up email for a specific alert.
        """
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert #{alert_id} not found.")
        if alert.status == "RESOLVED":
            raise ValueError(f"Alert #{alert_id} is already RESOLVED. Follow-up notifications can only be sent for unresolved alerts.")

        order = db.query(FactCustomerOrder).filter(FactCustomerOrder.customer_order_id == alert.customer_order_id).first()
        cust_name = order.customer.customer_name if (order and order.customer) else None
        prod_name = order.product.product_name if (order and order.product) else None
        prod_qty = order.order_qty if order else None
        req_date = str(order.requested_delivery_date) if (order and order.requested_delivery_date) else None
        app_date = str(order.confirmed_delivery_date or order.requested_delivery_date or "Pending Confirmation")

        first_log = db.query(EmailNotificationLog).filter(
            EmailNotificationLog.alert_id == alert.id,
            EmailNotificationLog.notification_type.in_(["ACTION_REQUIRED", "DELIVERY_RISK"]),
            EmailNotificationLog.status.in_(["SENT", "PENDING_CONFIG"]),
        ).order_by(EmailNotificationLog.created_at.asc()).first()

        first_time = (first_log.sent_at or first_log.created_at) if first_log else alert.detected_at
        now = utcnow()
        if first_time.tzinfo is None:
            first_time = first_time.replace(tzinfo=timezone.utc)
        days_unresolved = max(1, int((now - first_time).total_seconds() / 86400.0))
        first_str = first_time.strftime("%Y-%m-%d %H:%M UTC")

        logs = EmailService.send_followup_notification(
            db=db,
            alert=alert,
            days_unresolved=days_unresolved,
            first_email_date=first_str,
            customer_name=cust_name,
            product_name=prod_name,
            product_qty=prod_qty,
            required_date=req_date,
            approved_date=app_date,
            app_url=app_url,
            force_send=force_send,
        )

        return {
            "status": "SUCCESS",
            "alert_id": alert.id,
            "customer_order_id": alert.customer_order_id,
            "days_unresolved": days_unresolved,
            "emails_dispatched": len(logs),
            "logs": [{"id": l.id, "recipient": l.recipient_email, "category": l.recipient_category, "status": l.status} for l in logs],
        }

    @classmethod
    def _synthesize_risk_with_domo(
        cls,
        order_id: str,
        customer_name: str,
        product_name: str,
        approved_date: str,
        department: str,
        risk_category: str,
        severity: str,
        description: str,
        fallback_impact: Optional[str] = None,
        fallback_action: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Synthesizes detected operational risk using Domo AI Text Generation API.
        Generates contextual delivery impact and actionable mitigation recommendation.
        Falls back to provided deterministic defaults if Domo is unavailable or unconfigured.
        """
        from ..agent.domo_client import DomoTextLLM, is_domo_configured

        if not is_domo_configured():
            return fallback_impact, fallback_action

        prompt = (
            "You are Agent 3: Order Monitoring & Risk Surveillance Agent for an enterprise manufacturing system.\n"
            f"Analyze the following operational risk detected for customer order {order_id}:\n"
            f"- Customer: {customer_name}\n"
            f"- Product: {product_name}\n"
            f"- Approved Delivery Date: {approved_date}\n"
            f"- Department: {department}\n"
            f"- Category: {risk_category}\n"
            f"- Severity: {severity}\n"
            f"- Details: {description}\n\n"
            "Provide:\n"
            "1. Specific operational delivery impact (1 concise sentence describing impact on delivery milestone or line stoppage).\n"
            "2. Actionable mitigation action (1 concise sentence detailing immediate operational corrective action or escalation).\n\n"
            "Respond in valid JSON format:\n"
            "{\n"
            '  "delivery_impact": "...",\n'
            '  "recommended_action": "..."\n'
            "}\n"
            "Respond ONLY with valid JSON."
        )

        try:
            llm = DomoTextLLM(max_tokens=300, temperature=0.1)
            raw = llm.invoke(prompt)
            clean = raw.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```[a-zA-Z]*\n?", "", clean)
                clean = re.sub(r"\n?```$", "", clean).strip()
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                clean = m.group(0)
            data = json.loads(clean)
            impact = data.get("delivery_impact")
            action = data.get("recommended_action")
            return (
                str(impact).strip() if impact else fallback_impact,
                str(action).strip() if action else fallback_action,
            )
        except Exception:
            return fallback_impact, fallback_action


def notify_order_changed(order_id: str, db: Optional[Session] = None) -> List[RiskAlert]:
    """
    Internal event notification hook invoked when production order status,
    quality inspection disposition, or shipment status changes.
    Triggers an immediate focused event risk check for the impacted customer order.
    """
    if not order_id:
        return []
    if db is not None:
        return MonitoringService.run_event_check(db, order_id)
    from ..database import SessionLocal
    session = SessionLocal()
    try:
        return MonitoringService.run_event_check(session, order_id)
    finally:
        session.close()

