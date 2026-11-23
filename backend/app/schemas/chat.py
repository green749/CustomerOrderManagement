from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class ToolStep(BaseModel):
    step: Optional[int] = 1
    tool: str
    input: Dict[str, Any]
    output: Any
    thought: Optional[str] = None
    status: str = "success"


class DomoActionDecision(BaseModel):
    """Pydantic schema defining the structured decision output from Domo AI."""
    action: str = Field(..., description="Action to take: tool name, or 'final' for final response")
    thought: Optional[str] = Field(None, description="Reasoning or evaluation of current state")
    input: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters if action is a tool call")
    answer: Optional[str] = Field(None, description="Final markdown answer if action is 'final'")
    source_tables: Optional[List[str]] = Field(default_factory=list, description="Database tables referenced")
    recommended_action: Optional[str] = Field(None, description="Operational next action recommendation")
    confidence: Optional[str] = Field(default="HIGH", description="Confidence level HIGH, MEDIUM, LOW")


class DomoAgentFinalResult(BaseModel):
    """Pydantic schema defining the final validated agent response."""
    answer: str
    steps: List[ToolStep] = Field(default_factory=list)
    provider: str = "domo_ai"
    ai_available: bool = True
    confidence: str = "HIGH"
    source_tables: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    role: str
    content: str
    steps: Optional[List[ToolStep]] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[int] = None
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    steps: List[ToolStep] = []
    message_id: int
    created_at: datetime
    provider: str = "domo_ai"  # "domo_ai" | "deterministic_tool" | "ai_unavailable"
    ai_available: bool = True
    model_name: Optional[str] = "domo.domo_ai.domogpt-small-v2.1:anthropic"
