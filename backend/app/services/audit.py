from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent

def log_audit_event(
    db: Session,
    organization_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    user_id: Optional[str] = None,
    details: Optional[Any] = None
) -> AuditEvent:
    """
    Creates and commits an immutable audit log record.
    """
    event = AuditEvent(
        organization_id=organization_id,
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=details
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
