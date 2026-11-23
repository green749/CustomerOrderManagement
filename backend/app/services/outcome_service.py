import logging
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.business import FactCustomerOrder, FactShipmentMilestone
from ..models.workflow import CommitmentProposal, AgentOutcome
from ..repositories.audit_repo import AuditRepository
from .approval_policy_service import get_or_create_policy_engine_user

logger = logging.getLogger("manufacturing.services.outcome")


def utcnow():
    return datetime.now(timezone.utc)


class OutcomeService:
    """
    Service for tracking and recording delivery outcomes against autonomous
    and human commitment proposals.
    """

    @classmethod
    def record_delivery_outcome(
        cls,
        db: Session,
        customer_order_id: str,
        actual_delivery_date: Optional[date] = None,
    ) -> AgentOutcome:
        """
        Record delivery outcome when an order monitoring record closes as DELIVERED.
        Captures:
        - Promised date (from latest approved proposal, or confirmed date)
        - Actual delivery date
        - Variance in days (actual - promised)
        - Whether the commitment was met (variance <= 0)
        - Approval type: AUTO_APPROVED vs HUMAN_APPROVED
        """
        # Idempotency: check if outcome already recorded
        existing = db.query(AgentOutcome).filter(
            AgentOutcome.customer_order_id == customer_order_id
        ).first()
        if existing:
            return existing

        order = db.query(FactCustomerOrder).filter(
            FactCustomerOrder.customer_order_id == customer_order_id
        ).first()

        approved_prop = (
            db.query(CommitmentProposal)
            .filter(
                CommitmentProposal.customer_order_id == customer_order_id,
                CommitmentProposal.status == "APPROVED",
            )
            .order_by(CommitmentProposal.revision.desc(), CommitmentProposal.id.desc())
            .first()
        )

        # Resolve promised date
        if approved_prop and approved_prop.proposed_date:
            promised_date = approved_prop.proposed_date
        elif order and order.confirmed_delivery_date:
            promised_date = order.confirmed_delivery_date
        elif order and order.requested_delivery_date:
            promised_date = order.requested_delivery_date
        else:
            promised_date = date.today()

        # All proposals strictly require human approval
        approval_type = "HUMAN_APPROVED"

        # Resolve actual delivery date
        if actual_delivery_date is None:
            shipment = (
                db.query(FactShipmentMilestone)
                .filter(FactShipmentMilestone.customer_order_id == customer_order_id)
                .order_by(FactShipmentMilestone.dispatch_date.desc())
                .first()
            )
            if shipment and shipment.actual_delivery_ts:
                actual_delivery_date = shipment.actual_delivery_ts.date()
            else:
                actual_delivery_date = date.today()

        # Variance: positive means late, zero or negative means on-time/early
        variance_days = (actual_delivery_date - promised_date).days
        commitment_met = variance_days <= 0

        outcome = AgentOutcome(
            customer_order_id=customer_order_id,
            proposal_id=approved_prop.id if approved_prop else None,
            promised_date=promised_date,
            actual_delivery_date=actual_delivery_date,
            variance_days=variance_days,
            approval_type=approval_type,
            commitment_met=commitment_met,
            delivered_at=utcnow(),
            created_at=utcnow(),
        )
        db.add(outcome)
        db.commit()
        db.refresh(outcome)

        AuditRepository.log(
            db=db,
            action="RECORD_OUTCOME",
            entity="agent_outcome",
            entity_id=str(outcome.id),
            payload={
                "customer_order_id": customer_order_id,
                "promised_date": str(promised_date),
                "actual_delivery_date": str(actual_delivery_date),
                "variance_days": variance_days,
                "approval_type": approval_type,
                "commitment_met": commitment_met,
            },
        )
        logger.info(
            f"Outcome recorded for order {customer_order_id}: promised={promised_date}, "
            f"actual={actual_delivery_date}, variance={variance_days}d, type={approval_type}, met={commitment_met}"
        )
        return outcome

    @classmethod
    def list_outcomes(
        cls,
        db: Session,
        approval_type: Optional[str] = None,
        commitment_met: Optional[bool] = None,
        limit: int = 50,
    ) -> List[AgentOutcome]:
        q = db.query(AgentOutcome)
        if approval_type:
            q = q.filter(AgentOutcome.approval_type == approval_type)
        if commitment_met is not None:
            q = q.filter(AgentOutcome.commitment_met == commitment_met)
        return q.order_by(AgentOutcome.created_at.desc()).limit(limit).all()
