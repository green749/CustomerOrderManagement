from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models.chat import Conversation, Message


class ChatRepository:
    @staticmethod
    def get_conversations(
        db: Session,
        user_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = (
            db.query(
                Conversation.id,
                Conversation.user_id,
                Conversation.title,
                Conversation.created_at,
                Conversation.updated_at,
                func.count(Message.id).label("message_count"),
            )
            .outerjoin(Message, Conversation.id == Message.conversation_id)
        )
        if user_id:
            query = query.filter(Conversation.user_id == user_id)
        rows = (
            query.group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "title": r.title,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "message_count": r.message_count,
            }
            for r in rows
        ]

    @staticmethod
    def get_conversation_by_id(db: Session, conversation_id: str) -> Optional[Conversation]:
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()

    @staticmethod
    def create_conversation(
        db: Session,
        user_id: Optional[int] = None,
        title: str = "Customer Order Assistance",
        conversation_id: Optional[str] = None,
    ) -> Conversation:
        conv = Conversation(
            user_id=user_id,
            title=title,
        )
        if conversation_id:
            conv.id = conversation_id
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def get_messages(db: Session, conversation_id: str) -> List[Message]:
        return (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

    @staticmethod
    def add_message(
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        steps: Optional[list] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            steps=steps,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

