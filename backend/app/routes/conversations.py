from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.chat_service import ChatService
from ..schemas.chat import ConversationResponse, MessageResponse
from ..models.auth import User
from ..services.auth_service import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve chat conversations for the current authenticated user."""
    return ChatService.get_conversations(db, user_id=current_user.id)


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve message history and tool traces for a conversation."""
    return ChatService.get_messages(db, conversation_id)

