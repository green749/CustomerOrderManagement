from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.workflow import AgentAction


def utcnow():
    return datetime.now(timezone.utc)


class AgentActionRepository:
    """Repository for Agent 3 Corrective Action proposals and execution tracking."""

    @staticmethod
    def create_action(
        db: Session,
        customer_order_id: str,
        action_type: str,
        alert_id: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        requires_approval: bool = True,
        proposed_by: str = "agent3-monitoring",
        status: str = "PROPOSED",
    ) -> AgentAction:
        action = AgentAction(
            alert_id=alert_id,
            customer_order_id=customer_order_id,
            action_type=action_type,
            parameters=parameters or {},
            status=status,
            requires_approval=requires_approval,
            proposed_by=proposed_by,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        return action

    @staticmethod
    def get_action_by_id(db: Session, action_id: int) -> Optional[AgentAction]:
        return db.query(AgentAction).filter(AgentAction.id == action_id).first()

    @staticmethod
    def list_actions(
        db: Session,
        status: Optional[str] = None,
        customer_order_id: Optional[str] = None,
        action_type: Optional[str] = None,
        alert_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[AgentAction]:
        q = db.query(AgentAction)
        if status:
            q = q.filter(AgentAction.status == status.upper().strip())
        if customer_order_id:
            q = q.filter(AgentAction.customer_order_id == customer_order_id.strip())
        if action_type:
            q = q.filter(AgentAction.action_type == action_type.upper().strip())
        if alert_id:
            q = q.filter(AgentAction.alert_id == alert_id)
        return q.order_by(AgentAction.created_at.desc()).limit(limit).all()

    @staticmethod
    def find_existing_open_action(
        db: Session,
        customer_order_id: str,
        action_type: str,
        alert_id: Optional[int] = None,
    ) -> Optional[AgentAction]:
        """Find an open action (PROPOSED or APPROVED) with the same type for this order."""
        q = db.query(AgentAction).filter(
            AgentAction.customer_order_id == customer_order_id,
            AgentAction.action_type == action_type,
            AgentAction.status.in_(["PROPOSED", "APPROVED"]),
        )
        if alert_id is not None:
            q = q.filter(AgentAction.alert_id == alert_id)
        return q.first()

    @staticmethod
    def count_open_actions_for_order(db: Session, customer_order_id: str) -> int:
        return db.query(func.count(AgentAction.id)).filter(
            AgentAction.customer_order_id == customer_order_id,
            AgentAction.status.in_(["PROPOSED", "APPROVED"]),
        ).scalar() or 0

    @staticmethod
    def count_total_actions_for_order(db: Session, customer_order_id: str) -> int:
        return db.query(func.count(AgentAction.id)).filter(
            AgentAction.customer_order_id == customer_order_id,
        ).scalar() or 0

    @staticmethod
    def count_daily_actions(db: Session) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return db.query(func.count(AgentAction.id)).filter(
            AgentAction.created_at >= today_start,
        ).scalar() or 0

    @staticmethod
    def update_action_status(
        db: Session,
        action: AgentAction,
        status: str,
        approved_by: Optional[int] = None,
        executed_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> AgentAction:
        action.status = status
        if approved_by is not None:
            action.approved_by = approved_by
        if executed_at is not None:
            action.executed_at = executed_at
        if result is not None:
            action.result = result
        action.updated_at = utcnow()
        db.commit()
        db.refresh(action)
        return action
