import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..security.permissions import require_permission, Permission
from ..services.auth_service import get_current_user
from ..repositories.agent_action_repo import AgentActionRepository
from ..services.agent_action_service import AgentActionService
from ..schemas.workflow import AgentActionResponse, AgentActionDecisionRequest

logger = logging.getLogger("manufacturing.routes.actions")

router = APIRouter(prefix="/api/actions", tags=["Agent Corrective Actions"])


@router.get("", response_model=List[AgentActionResponse])
def list_actions(
    status: Optional[str] = Query(None, description="Filter by status (PROPOSED, APPROVED, EXECUTED, REJECTED, FAILED)"),
    customer_order_id: Optional[str] = Query(None, description="Filter by customer order ID"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    alert_id: Optional[int] = Query(None, description="Filter by risk alert ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALERT_VIEW)),
):
    """List proposed and executed Agent 3 corrective actions."""
    return AgentActionRepository.list_actions(
        db=db,
        status=status,
        customer_order_id=customer_order_id,
        action_type=action_type,
        alert_id=alert_id,
    )


@router.get("/{action_id}", response_model=AgentActionResponse)
def get_action_by_id(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALERT_VIEW)),
):
    """Retrieve details of a single agent action."""
    action = AgentActionRepository.get_action_by_id(db, action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent action #{action_id} not found."
        )
    return action


@router.post("/{action_id}/approve", response_model=AgentActionResponse)
def approve_action(
    action_id: int,
    payload: Optional[AgentActionDecisionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve and execute a proposed agent action."""
    try:
        return AgentActionService.approve_action(db=db, action_id=action_id, user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to approve action #{action_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{action_id}/reject", response_model=AgentActionResponse)
def reject_action(
    action_id: int,
    payload: Optional[AgentActionDecisionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject a proposed agent action."""
    try:
        reason = payload.reason if payload else None
        return AgentActionService.reject_action(db=db, action_id=action_id, user=current_user, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reject action #{action_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
