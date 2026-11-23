import os
import json
import logging
import threading
from datetime import date, datetime, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session, object_session
from sqlalchemy import func, or_

from ..config import settings
from ..models.auth import User
from ..models.business import DimCustomer
from ..models.workflow import OrderAssessment, CommitmentProposal
from ..repositories.audit_repo import AuditRepository

logger = logging.getLogger("manufacturing.services.approval_policy")

# ------------------------------------------------------------------------------
# GLOBAL AGENT KILL SWITCH REGISTRY
# ------------------------------------------------------------------------------
_KILL_SWITCH_LOCK = threading.Lock()
_PAUSED_AGENTS: Dict[str, Dict[str, Any]] = {}


def _normalize_agent_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def is_agent_paused(agent_name: str) -> bool:
    norm = _normalize_agent_name(agent_name)
    with _KILL_SWITCH_LOCK:
        rec = _PAUSED_AGENTS.get(norm)
        if rec and rec.get("paused"):
            return True
        # If generic policy names match
        if norm in ("approval-policy", "policy-engine", "auto-approval"):
            for alt in ("approval-policy", "policy-engine", "auto-approval"):
                if _PAUSED_AGENTS.get(alt, {}).get("paused"):
                    return True
        return False


def pause_agent(agent_name: str, paused_by_user_id: Optional[int] = None, reason: Optional[str] = None) -> Dict[str, Any]:
    norm = _normalize_agent_name(agent_name)
    now = datetime.now(timezone.utc)
    with _KILL_SWITCH_LOCK:
        _PAUSED_AGENTS[norm] = {
            "agent": norm,
            "paused": True,
            "paused_at": now.isoformat(),
            "paused_by": paused_by_user_id,
            "reason": reason or "Administrative pause via kill switch",
        }
    logger.warning(f"Agent '{norm}' paused by user {paused_by_user_id}")
    return {
        "agent": norm,
        "status": "PAUSED",
        "message": f"Agent '{norm}' has been paused.",
        "paused_at": now.isoformat(),
    }


def resume_agent(agent_name: str, resumed_by_user_id: Optional[int] = None) -> Dict[str, Any]:
    norm = _normalize_agent_name(agent_name)
    now = datetime.now(timezone.utc)
    with _KILL_SWITCH_LOCK:
        if norm in _PAUSED_AGENTS:
            _PAUSED_AGENTS[norm]["paused"] = False
            _PAUSED_AGENTS[norm]["resumed_at"] = now.isoformat()
            _PAUSED_AGENTS[norm]["resumed_by"] = resumed_by_user_id
    logger.info(f"Agent '{norm}' resumed by user {resumed_by_user_id}")
    return {
        "agent": norm,
        "status": "ACTIVE",
        "message": f"Agent '{norm}' has been resumed.",
        "resumed_at": now.isoformat(),
    }


def get_agent_status(agent_name: str) -> Dict[str, Any]:
    norm = _normalize_agent_name(agent_name)
    paused = is_agent_paused(norm)
    with _KILL_SWITCH_LOCK:
        info = _PAUSED_AGENTS.get(norm, {})
    return {
        "agent": norm,
        "status": "PAUSED" if paused else "ACTIVE",
        "details": info,
    }


def get_all_agents_status() -> List[Dict[str, Any]]:
    agents = ["agent1", "agent2", "agent3", "policy-engine", "intake-watcher"]
    with _KILL_SWITCH_LOCK:
        for k in _PAUSED_AGENTS.keys():
            if k not in agents:
                agents.append(k)
    return [get_agent_status(a) for a in agents]


# ------------------------------------------------------------------------------
# SYSTEM USER IDENTITY: policy-engine
# ------------------------------------------------------------------------------
def get_or_create_policy_engine_user(db: Session) -> User:
    """
    Ensure the dedicated 'policy-engine' system user identity exists.
    Maintains strict segregation of duties from 'agent2-system'.
    """
    email = "policy-engine@manufacturing.internal"
    user = db.query(User).filter(
        or_(User.email == email, User.email == "policy-engine")
    ).first()

    if not user:
        import os
        import uuid
        from .auth_service import hash_password
        system_secret = os.getenv("SYSTEM_USER_PASSWORD") or uuid.uuid4().hex
        user = User(
            email=email,
            full_name="Policy Auto-Approval Engine",
            hashed_password=hash_password(system_secret),
            role="system",
            department="COMMERCIAL",
            can_approve_commitments=True,
            is_active=True,
            customer_scope=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ------------------------------------------------------------------------------
# APPROVAL POLICY SERVICE
# ------------------------------------------------------------------------------
class ApprovalPolicyService:
    """
    Commercial commitment policy engine.
    AUTOMATIC APPROVAL IS PERMANENTLY DISABLED:
    All customer orders and proposals generated by Agent 2 strictly require human commercial approval.
    """

    @classmethod
    def is_enabled(cls) -> bool:
        # Automatic approval is disabled permanently across the entire application
        return False

    @classmethod
    def get_max_value_inr(cls) -> float:
        return 0.0

    @classmethod
    def get_max_per_day(cls) -> int:
        return 0

    @classmethod
    def get_daily_approved_count(cls, db: Session, policy_user_id: Optional[int] = None) -> int:
        """Count how many proposals were auto-approved today (always 0 since auto-approval is removed)."""
        return 0

    @classmethod
    def evaluate(
        cls,
        proposal: CommitmentProposal,
        assessment: OrderAssessment,
        customer: Optional[DimCustomer] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate proposal against approval policy.
        All customer orders and Agent 2 proposals require human approval.
        """
        return {
            "decision": "NEEDS_HUMAN",
            "reasons": ["Auto-approval from Agent 2 is permanently disabled: all customer orders require human approval"],
        }

    @classmethod
    def evaluate_and_apply(
        cls,
        db: Session,
        proposal: CommitmentProposal,
        assessment: OrderAssessment,
        customer: Optional[DimCustomer] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate and apply approval policy:
        All proposals remain in PENDING status for mandatory Human Commercial Review.
        """
        policy_user = get_or_create_policy_engine_user(db)
        reasons = ["Auto-approval from Agent 2 is permanently disabled: all customer orders require human approval"]

        is_low_confidence = (
            assessment is not None
            and getattr(assessment, "confidence_level", "").upper() == "LOW"
        )
        if is_low_confidence:
            reasons.append("Assessment confidence is LOW: requires mandatory human escalation")

        # Ensure proposal remains PENDING
        proposal.status = "PENDING"
        existing_reasons = list(proposal.reasons or [])
        item = "Mandatory Human Approval: All customer orders require human approval"
        if item not in existing_reasons:
            existing_reasons.append(item)
        for r in reasons:
            if r not in existing_reasons:
                existing_reasons.append(r)
        proposal.reasons = existing_reasons
        db.commit()
        db.refresh(proposal)

        AuditRepository.log(
            db=db,
            action="POLICY_ESCALATE",
            entity="commitment_proposal",
            entity_id=str(proposal.id),
            user_id=policy_user.id,
            payload={
                "decision": "NEEDS_HUMAN",
                "customer_order_id": proposal.customer_order_id,
                "reasons": reasons,
            },
        )
        logger.info(f"Proposal #{proposal.id} for order {proposal.customer_order_id} routed for human review.")

        if is_low_confidence:
            try:
                from .agent_controls_service import AgentControlsService
                AgentControlsService.escalate_item(
                    db=db,
                    customer_order_id=proposal.customer_order_id,
                    reason=f"Policy Escalation (NEEDS_HUMAN): {', '.join(reasons)}",
                    agent_name="policy-engine",
                    details={"proposal_id": proposal.id, "reasons": reasons, "decision": "NEEDS_HUMAN"},
                )
            except Exception as esc_err:
                logger.warning(f"Error sending policy escalation email: {esc_err}")

        return {"decision": "NEEDS_HUMAN", "proposal": proposal, "reasons": reasons}


# Convenience top-level module function matching prompt specification
evaluate = ApprovalPolicyService.evaluate
