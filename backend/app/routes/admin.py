from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..security.permissions import require_admin
from ..services.approval_policy_service import (
    pause_agent,
    resume_agent,
    get_agent_status,
    get_all_agents_status,
)
from ..repositories.audit_repo import AuditRepository

admin_router = APIRouter(prefix="/api/admin", tags=["Administration & Agent Governance"])


class AgentActionRequest(BaseModel):
    reason: Optional[str] = None


@admin_router.post("/agents/{agent}/pause")
def pause_agent_endpoint(
    agent: str,
    body: Optional[AgentActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Pause an agent globally (kill switch).
    Restricted to Administrator role.
    """
    reason = body.reason if body else None
    res = pause_agent(agent_name=agent, paused_by_user_id=current_user.id, reason=reason)
    AuditRepository.log(
        db=db,
        action="PAUSE_AGENT",
        entity="agent",
        entity_id=agent,
        user_id=current_user.id,
        payload={"agent": agent, "status": "PAUSED", "reason": reason},
    )
    return res


@admin_router.post("/agents/{agent}/resume")
def resume_agent_endpoint(
    agent: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Resume an agent globally.
    Restricted to Administrator role.
    """
    res = resume_agent(agent_name=agent, resumed_by_user_id=current_user.id)
    AuditRepository.log(
        db=db,
        action="RESUME_AGENT",
        entity="agent",
        entity_id=agent,
        user_id=current_user.id,
        payload={"agent": agent, "status": "ACTIVE"},
    )
    return res


@admin_router.get("/agents/status")
def list_agents_status(
    current_user: User = Depends(require_admin),
):
    """Get status of all managed agents and policy engines."""
    return get_all_agents_status()


@admin_router.get("/agents/{agent}/status")
def get_single_agent_status(
    agent: str,
    current_user: User = Depends(require_admin),
):
    """Get status of a specific agent."""
    return get_agent_status(agent)


@admin_router.get("/agents/overview")
def get_agents_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Get consolidated governance overview for Agent 1, 2, 3 and Policy Engine:
    - Running / paused status
    - Last run times
    - Counts of assessments, auto-approvals, alerts, actions, escalations
    - Governor limit thresholds and current utilization
    """
    from ..services.agent_controls_service import AgentControlsService
    return AgentControlsService.get_agent_governance_overview(db=db)

