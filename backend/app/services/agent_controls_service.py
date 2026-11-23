import os
import json
import time
import logging
import hashlib
import threading
from datetime import datetime, date, timedelta, timezone
from collections import deque
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, cast, String

from ..config import settings
from ..models.workflow import RiskAlert, AuditLog, OrderAssessment, CommitmentProposal, AgentAction, AgentOutcome
from ..repositories.audit_repo import AuditRepository
from .approval_policy_service import pause_agent, resume_agent, is_agent_paused, get_agent_status, ApprovalPolicyService
from .email_service import EmailService

logger = logging.getLogger("manufacturing.services.agent_controls")


def utcnow():
    return datetime.now(timezone.utc)


class AgentControlsService:
    """
    Cross-Cutting Controls and Governance for Autonomous Agents:
    1. Confidence & Escalation: Handles LOW confidence and double validation failures (NEEDS_HUMAN).
    2. Limits & Boundary Enforcement:
       - Max LLM calls per hour
       - Max auto-actions per day
       - Max cost per cycle
       Automatically pauses violating agent and raises admin alert.
    3. Status, metric aggregation, and audit logging.
    """

    _LOCK = threading.Lock()
    # In-memory store: agent_name -> deque of float timestamps
    _LLM_CALL_TIMESTAMPS: Dict[str, deque] = {
        "agent1": deque(),
        "agent2": deque(),
        "agent3": deque(),
        "all": deque(),
    }
    # In-memory cycle cost tracker
    _CYCLE_COSTS: Dict[str, float] = {}

    # --------------------------------------------------------------------------
    # SETTINGS RESOLUTION
    # --------------------------------------------------------------------------
    @classmethod
    def get_max_llm_calls_per_hour(cls) -> int:
        raw = os.environ.get("MAX_LLM_CALLS_PER_HOUR")
        if raw is not None:
            try:
                return int(raw)
            except ValueError:
                pass
        return getattr(settings, "max_llm_calls_per_hour", 100)

    @classmethod
    def get_max_auto_actions_per_day(cls) -> int:
        raw = os.environ.get("MAX_AUTO_ACTIONS_PER_DAY")
        if raw is not None:
            try:
                return int(raw)
            except ValueError:
                pass
        return getattr(settings, "max_auto_actions_per_day", 50)

    @classmethod
    def get_max_cost_per_cycle(cls) -> float:
        raw = os.environ.get("MAX_COST_PER_CYCLE")
        if raw is not None:
            try:
                return float(raw)
            except ValueError:
                pass
        return getattr(settings, "max_cost_per_cycle", 5.0)

    # --------------------------------------------------------------------------
    # RATE LIMITING & BOUNDARY TRACKING
    # --------------------------------------------------------------------------
    @classmethod
    def record_llm_call(cls, agent_name: str = "agent1", count: int = 1):
        """Records an LLM call timestamp for hourly sliding window rate limiting."""
        now = time.time()
        norm = agent_name.lower().replace("_", "-")
        with cls._LOCK:
            if norm not in cls._LLM_CALL_TIMESTAMPS:
                cls._LLM_CALL_TIMESTAMPS[norm] = deque()
            for _ in range(count):
                cls._LLM_CALL_TIMESTAMPS[norm].append(now)
                cls._LLM_CALL_TIMESTAMPS["all"].append(now)

    @classmethod
    def get_llm_calls_last_hour(cls, agent_name: Optional[str] = None) -> int:
        now = time.time()
        cutoff = now - 3600.0
        with cls._LOCK:
            target = "all" if not agent_name else agent_name.lower().replace("_", "-")
            dq = cls._LLM_CALL_TIMESTAMPS.get(target, deque())
            # Prune older than 1 hr
            while dq and dq[0] < cutoff:
                dq.popleft()
            return len(dq)

    @classmethod
    def check_and_enforce_llm_call_limit(cls, db: Session, agent_name: str) -> bool:
        """
        Check if agent has exceeded max LLM calls per hour.
        If exceeded, pauses the agent, raises an admin alert, and returns False (blocked).
        """
        limit = cls.get_max_llm_calls_per_hour()
        current_calls = cls.get_llm_calls_last_hour(agent_name)
        if current_calls >= limit:
            msg = f"Agent '{agent_name}' exceeded maximum allowed LLM calls per hour ({current_calls}/{limit})."
            cls.raise_admin_alert(db=db, agent_name=agent_name, limit_type="MAX_LLM_CALLS_PER_HOUR", message=msg)
            return False
        return True

    @classmethod
    def check_and_enforce_auto_actions_limit(cls, db: Session, agent_name: str = "agent3") -> bool:
        """
        Check if daily auto-actions limit has been reached.
        If exceeded, pauses agent, raises admin alert, and returns False.
        """
        limit = cls.get_max_auto_actions_per_day()
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_actions_count = db.query(AgentAction).filter(
            AgentAction.created_at >= today_start,
            AgentAction.status.in_(["PROPOSED", "APPROVED", "EXECUTED"]),
        ).count()

        if daily_actions_count >= limit:
            msg = f"Agent '{agent_name}' reached daily auto-action governor limit ({daily_actions_count}/{limit})."
            cls.raise_admin_alert(db=db, agent_name=agent_name, limit_type="MAX_AUTO_ACTIONS_PER_DAY", message=msg)
            return False
        return True

    @classmethod
    def check_and_enforce_cycle_cost_limit(cls, db: Session, agent_name: str, cycle_cost: float) -> bool:
        """
        Check if cycle cost limit has been exceeded.
        If exceeded, pauses agent, raises admin alert, and returns False.
        """
        limit = cls.get_max_cost_per_cycle()
        if cycle_cost > limit:
            msg = f"Agent '{agent_name}' exceeded maximum cost per cycle (${cycle_cost:.2f} > ${limit:.2f})."
            cls.raise_admin_alert(db=db, agent_name=agent_name, limit_type="MAX_COST_PER_CYCLE", message=msg)
            return False
        return True

    # --------------------------------------------------------------------------
    # ADMIN ALERT & KILL SWITCH
    # --------------------------------------------------------------------------
    @classmethod
    def raise_admin_alert(
        cls,
        db: Session,
        agent_name: str,
        limit_type: str,
        message: str,
    ) -> RiskAlert:
        """
        When an agent limit is hit:
        1. Pause the offending agent via kill switch
        2. Create an admin RiskAlert
        3. Dispatch an email notification to the Admin
        4. Write to AuditLog with reasoning
        """
        norm_agent = agent_name.lower().replace("_", "-")
        # 1. Pause agent
        pause_agent(norm_agent, reason=f"Governor limit exceeded: {limit_type}. {message}")

        # 2. Fingerprint & Alert creation
        fp_raw = f"ADMIN_ALERT:{norm_agent}:{limit_type}:{datetime.now().strftime('%Y-%m-%d-%H')}"
        fp = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()

        existing_alert = db.query(RiskAlert).filter(
            RiskAlert.department == "ADMIN",
            RiskAlert.risk_category == "LIMIT_EXCEEDED",
            RiskAlert.dedup_fingerprint == fp,
            RiskAlert.status == "OPEN",
        ).first()

        if not existing_alert:
            admin_alert = RiskAlert(
                customer_order_id="SYSTEM",
                department="ADMIN",
                risk_category="LIMIT_EXCEEDED",
                severity="CRITICAL",
                title=f"[ADMIN ALERT] {norm_agent.upper()} Governor Limit Exceeded: {limit_type}",
                description=message,
                delivery_impact=f"Autonomous processing for {norm_agent} suspended until administrator review.",
                recommended_action="Access Agent Control dashboard, inspect metrics, and resume agent when safe.",
                status="OPEN",
                dedup_fingerprint=fp,
                detected_at=utcnow(),
            )
            db.add(admin_alert)
            db.commit()
            db.refresh(admin_alert)
        else:
            admin_alert = existing_alert

        # 3. Log audit event
        AuditRepository.log(
            db=db,
            action="ADMIN_ALERT_RAISED",
            entity="agent_limit",
            entity_id=norm_agent,
            payload={
                "agent": norm_agent,
                "limit_type": limit_type,
                "message": message,
                "alert_id": admin_alert.id,
                "status": "PAUSED",
            },
        )

        # 4. Dispatch Email to Admin
        try:
            EmailService.send_admin_alert(
                db=db,
                agent_name=norm_agent,
                limit_type=limit_type,
                message=message,
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch admin email alert: {e}")

        logger.critical(f"ADMIN ALERT RAISED: {norm_agent} paused due to {limit_type} - {message}")
        return admin_alert

    # --------------------------------------------------------------------------
    # CONFIDENCE & ESCALATION (NEEDS_HUMAN)
    # --------------------------------------------------------------------------
    @classmethod
    def escalate_item(
        cls,
        db: Session,
        customer_order_id: str,
        reason: str,
        agent_name: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Requirement 1:
        If an agent result has confidence LOW, or LLM output fails validation twice:
        - Mark item NEEDS_HUMAN
        - Notify customer service contact via EmailService instead of acting
        - Record decision in audit log with reasoning
        """
        logger.warning(f"ESCALATION TRIGGERED on order {customer_order_id} by {agent_name}: {reason}")

        # Send email to Customer Service contact
        try:
            EmailService.send_escalation_notification(
                db=db,
                customer_order_id=customer_order_id,
                reason=reason,
                agent_name=agent_name,
                details=details,
            )
        except Exception as mail_err:
            logger.warning(f"Failed to send Customer Service escalation notification: {mail_err}")

        # Log audit entry
        AuditRepository.log(
            db=db,
            action="AGENT_ESCALATION",
            entity=agent_name,
            entity_id=customer_order_id,
            payload={
                "decision": "NEEDS_HUMAN",
                "reason": reason,
                "agent": agent_name,
                "details": details or {},
                "timestamp": utcnow().isoformat(),
            },
        )

    # --------------------------------------------------------------------------
    # GOVERNANCE OVERVIEW AGGREGATOR
    # --------------------------------------------------------------------------
    @classmethod
    def get_agent_governance_overview(cls, db: Session) -> Dict[str, Any]:
        """
        Aggregates live runtime state for Agent 1, Agent 2, Agent 3, and Policy Engine:
        - Running / Paused status
        - Last run time
        - Counts: assessments, auto-approvals, alerts, actions, escalations
        - Governor limit consumption and thresholds
        """
        # Base counts
        total_assessments = db.query(OrderAssessment).count()
        total_alerts = db.query(RiskAlert).count()
        total_actions = db.query(AgentAction).count()

        auto_approvals_count = db.query(CommitmentProposal).filter(
            CommitmentProposal.status == "APPROVED",
            or_(
                CommitmentProposal.decision_note.ilike("%auto-approved%"),
                CommitmentProposal.decision_note.ilike("%policy%"),
            ),
        ).count()

        escalations_count = db.query(AuditLog).filter(
            or_(
                AuditLog.action == "AGENT_ESCALATION",
                AuditLog.action == "POLICY_EVALUATION_NEEDS_HUMAN",
                cast(AuditLog.payload, String).like("%NEEDS_HUMAN%"),
            )
        ).count()

        # Last run times from AuditLog
        def get_last_run(entity_names: List[str]) -> Optional[str]:
            row = (
                db.query(AuditLog)
                .filter(AuditLog.entity.in_(entity_names))
                .order_by(AuditLog.created_at.desc())
                .first()
            )
            return row.created_at.isoformat() if row and row.created_at else None

        agent1_last = get_last_run(["agent1", "conversations", "chat_agent"])
        agent2_last = get_last_run(["feasibility_agent", "assessment", "agent2"])

        # Agent 3: Query MonitoringExecutionLog for actual 24-hour cycle history
        from ..models.workflow import MonitoringExecutionLog
        from .monitoring_service import _MONITORING_LOCK
        
        last_mon_log = (
            db.query(MonitoringExecutionLog)
            .order_by(MonitoringExecutionLog.executed_at.desc())
            .first()
        )
        if last_mon_log and last_mon_log.executed_at:
            agent3_last = last_mon_log.executed_at.isoformat()
            agent3_next_run = (last_mon_log.executed_at + timedelta(days=1)).isoformat()
        else:
            agent3_last = get_last_run(["monitoring_agent", "monitoring", "agent3", "agent_action"])
            agent3_next_run = (utcnow() + timedelta(days=1)).isoformat()

        # Operational status for Agent 3:
        # Agent 3 is scheduled to run once every 24 hours. When not actively executing a cycle,
        # it is in SCHEDULED status waiting for its daily interval, rather than showing "RUNNING".
        if is_agent_paused("agent3"):
            agent3_status = "PAUSED"
        elif _MONITORING_LOCK.locked():
            agent3_status = "RUNNING"
        else:
            agent3_status = "SCHEDULED"

        policy_last = get_last_run(["approval_policy", "policy-engine"])

        agents_data = [
            {
                "id": "agent1",
                "name": "Agent 1: Order Chat Agent",
                "role": "ReAct conversational assistant & intent extractor",
                "status": "PAUSED" if is_agent_paused("agent1") else "RUNNING",
                "last_run": agent1_last,
                "metrics": {
                    "llm_calls_last_hour": cls.get_llm_calls_last_hour("agent1"),
                },
                "details": get_agent_status("agent1").get("details", {}),
            },
            {
                "id": "agent2",
                "name": "Agent 2: Feasibility & Commitment Agent",
                "role": "7-department readiness assessor & critical path solver",
                "status": "PAUSED" if is_agent_paused("agent2") else "RUNNING",
                "last_run": agent2_last,
                "metrics": {
                    "total_assessments": total_assessments,
                    "llm_calls_last_hour": cls.get_llm_calls_last_hour("agent2"),
                },
                "details": get_agent_status("agent2").get("details", {}),
            },
            {
                "id": "agent3",
                "name": "Agent 3: Monitoring & Surveillance Agent",
                "role": "Daily operational surveillance & risk radar (Runs once every 24 hours)",
                "status": agent3_status,
                "last_run": agent3_last,
                "next_run": agent3_next_run,
                "schedule": "Once every 24 hours (Daily)",
                "interval_seconds": 86400,
                "metrics": {
                    "schedule": "Once / 24h",
                    "total_alerts": total_alerts,
                    "total_actions": total_actions,
                    "llm_calls_last_hour": cls.get_llm_calls_last_hour("agent3"),
                },
                "details": {
                    **get_agent_status("agent3").get("details", {}),
                    "frequency": "Once every 24 hours (Daily)",
                    "schedule": "Once every 24 hours (Daily)",
                    "next_run": agent3_next_run,
                },
            },
            {
                "id": "policy-engine",
                "name": "Commercial Approval Policy Gate",
                "role": "Deterministic policy-based commercial commitment approval (100% Human Sign-Off)",
                "status": "DISABLED" if not ApprovalPolicyService.is_enabled() else ("PAUSED" if is_agent_paused("policy-engine") else "RUNNING"),
                "last_run": policy_last,
                "metrics": {
                    "auto_approvals": 0,
                    "escalations": escalations_count,
                },
                "details": get_agent_status("policy-engine").get("details", {}),
            },
        ]

        limits = {
            "max_llm_calls_per_hour": cls.get_max_llm_calls_per_hour(),
            "max_auto_actions_per_day": cls.get_max_auto_actions_per_day(),
            "max_cost_per_cycle": cls.get_max_cost_per_cycle(),
            "current_llm_calls_hour": cls.get_llm_calls_last_hour("all"),
        }

        return {
            "agents": agents_data,
            "limits": limits,
            "counts": {
                "assessments": total_assessments,
                "auto_approvals": 0,
                "alerts": total_alerts,
                "actions": total_actions,
                "escalations": escalations_count,
            },
        }
