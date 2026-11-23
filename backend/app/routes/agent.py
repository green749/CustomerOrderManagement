from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.chat_service import ChatService
from ..schemas.chat import ChatRequest, ChatResponse
from ..models.auth import User
from ..services.auth_service import get_current_user

import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.chat_service import ChatService
from ..schemas.chat import ChatRequest, ChatResponse
from ..models.auth import User
from ..models.workflow import AgentRun
from ..schemas.workflow import AgentRunResponse
from ..services.auth_service import get_current_user
from ..agent.domo_client import is_domo_configured
from ..config import settings
from ..services.agent_controls_service import AgentControlsService

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])
agents_router = APIRouter(tags=["AI Agents"])


@router.get("/status")
@agents_router.get("/agents/status")
@agents_router.get("/api/agents/status")
def get_agents_status(db: Session = Depends(get_db)):
    """
    Get current runtime status of AI agents, configuration modes, and rate limits.
    """
    feasibility_mode = os.environ.get(
        "FEASIBILITY_AGENT_MODE", getattr(settings, "feasibility_agent_mode", "agentic")
    ).strip().lower()
    monitoring_mode = os.environ.get(
        "MONITORING_AGENT_MODE", getattr(settings, "monitoring_agent_mode", "agentic")
    ).strip().lower()
    domo_ok = is_domo_configured()
    hourly_calls = AgentControlsService.get_llm_calls_last_hour()
    max_hourly = AgentControlsService.get_max_llm_calls_per_hour()
    return {
        "feasibility_mode": feasibility_mode,
        "monitoring_mode": monitoring_mode,
        "is_domo_configured": domo_ok,
        "domo_model": settings.domo_model if domo_ok else None,
        "hourly_llm_limit_active": (hourly_calls >= max_hourly),
        "llm_calls_last_hour": hourly_calls,
        "max_llm_calls_per_hour": max_hourly,
    }


@router.get("/runs", response_model=List[AgentRunResponse])
@agents_router.get("/agents/runs", response_model=List[AgentRunResponse])
@agents_router.get("/api/agents/runs", response_model=List[AgentRunResponse])
def get_agent_runs(
    customer_order_id: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Query historical and live AgentRun records including step-by-step reasoning and tool calls.
    """
    query = db.query(AgentRun)
    if customer_order_id:
        query = query.filter(AgentRun.customer_order_id == customer_order_id)
    target_agent = agent_name or agent
    if target_agent:
        query = query.filter(AgentRun.agent_name == target_agent)
    return query.order_by(AgentRun.created_at.desc()).limit(limit).all()


@router.post("/chat", response_model=ChatResponse)
def agent_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Interact with the Customer Order Management Agent.
    Runs the controlled JSON-action loop with Domo Text Generation API and read-only tools.
    """
    return ChatService.handle_chat(
        db=db,
        message_text=request.message,
        conversation_id=request.conversation_id,
        user_id=current_user.id,
    )

