from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models.workflow import AuditLog


class AuditRepository:
    @staticmethod
    def log(
        db: Session,
        action: str,
        entity: str,
        entity_id: Optional[str] = None,
        user_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> AuditLog:
        """Create an immutable audit log record."""
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            payload=payload,
        )
        db.add(entry)
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
        return entry

