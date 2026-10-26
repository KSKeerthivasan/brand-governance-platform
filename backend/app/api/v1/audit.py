from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventOut
from app.api.deps import require_any_member

router = APIRouter()

@router.get("", response_model=List[AuditEventOut])
def list_audit_events(
    event_type: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    query = db.query(AuditEvent).filter(
        AuditEvent.organization_id == membership.organization_id
    )

    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)

    events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()

    result = []
    for e in events:
        user = db.query(User).filter(User.id == e.user_id).first() if e.user_id else None
        result.append(AuditEventOut(
            id=e.id,
            organization_id=e.organization_id,
            user_id=e.user_id,
            user_name=user.full_name if user else "System",
            event_type=e.event_type,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            summary=e.summary,
            details=e.details,
            created_at=e.created_at
        ))

    return result
