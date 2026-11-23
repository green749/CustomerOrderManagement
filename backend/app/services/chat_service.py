from typing import Optional, List, Tuple
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..repositories.chat_repo import ChatRepository
from ..models.chat import Conversation, Message
from ..schemas.chat import (
    ConversationResponse,
    MessageResponse,
    ChatResponse,
    ToolStep,
)
class ChatService:
    @staticmethod
    def get_conversations(db: Session, user_id: Optional[int] = None) -> List[ConversationResponse]:
        convs = ChatRepository.get_conversations(db, user_id=user_id)
        return [
            ConversationResponse(
                id=c["id"],
                user_id=c["user_id"],
                title=c["title"],
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                message_count=c["message_count"],
            )
            for c in convs
        ]

    @staticmethod
    def get_messages(db: Session, conversation_id: str) -> List[MessageResponse]:
        conv = ChatRepository.get_conversation_by_id(db, conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conversation_id}' not found",
            )
        messages = ChatRepository.get_messages(db, conversation_id)
        return [MessageResponse.model_validate(m) for m in messages]

    @staticmethod
    def handle_chat(
        db: Session,
        message_text: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> ChatResponse:
        from ..agent.agent_loop import run_agent_loop
        # Resolve or create conversation
        conv = None
        if conversation_id:
            conv = ChatRepository.get_conversation_by_id(db, conversation_id)

        if not conv:
            # Create descriptive title from initial user message
            title = message_text.strip()[:40]
            if len(message_text.strip()) > 40:
                title += "..."
            conv = ChatRepository.create_conversation(
                db,
                user_id=user_id,
                title=title or "Order Inquiry",
                conversation_id=conversation_id,
            )

        # 1. Save user message
        ChatRepository.add_message(
            db,
            conversation_id=conv.id,
            role="user",
            content=message_text,
        )

        # 2. Build history
        past_messages = ChatRepository.get_messages(db, conv.id)
        history = [
            {"role": m.role, "content": m.content}
            for m in past_messages[:-1]  # exclude the user message just added
        ]

        # 3. Run Agent loop
        from ..agent.agent_loop import _clean_final_answer
        answer, steps, provider, ai_available = run_agent_loop(
            db=db,
            question=message_text,
            history=history,
            max_steps=5,
            user_id=user_id,
        )

        # Ensure answer is strictly human-facing and free of internal agent thoughts / JSON
        clean_answer = _clean_final_answer(answer)

        # 4. Save assistant response with tool execution traces
        assistant_msg = ChatRepository.add_message(
            db,
            conversation_id=conv.id,
            role="assistant",
            content=clean_answer,
            steps=steps,
        )

        # Update conversation timestamp
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()

        tool_steps = [
            ToolStep(
                step=s.get("step", 1),
                tool=s.get("tool", "unknown_tool"),
                input=s.get("input", {}),
                output=s.get("output", {}),
                thought=s.get("thought"),
                status=s.get("status", "success"),
            )
            for s in steps
        ]

        return ChatResponse(
            conversation_id=conv.id,
            answer=clean_answer,
            steps=tool_steps,
            message_id=assistant_msg.id,
            created_at=assistant_msg.created_at,
            provider=provider,
            ai_available=ai_available,
        )
