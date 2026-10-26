import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class AuditEvent(Base):
    """
    Structured audit event log capturing significant state transitions and actions.
    """
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    event_type = Column(String(100), nullable=False, index=True)
    # e.g., KNOWLEDGE_UPLOADED, KNOWLEDGE_APPROVED, KNOWLEDGE_REJECTED,
    # CONTENT_CREATED, CONTENT_REVISED, GOVERNANCE_CHECK_RUN,
    # APPROVAL_SUBMITTED, APPROVAL_DECIDED, ROLE_CHANGED
    
    entity_type = Column(String(50), nullable=False)  # knowledge_source, rule, fact, content_item, content_version, submission
    entity_id = Column(String(36), nullable=False)
    summary = Column(String(255), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    organization = relationship("Organization", back_populates="audit_events")
    user = relationship("User")
