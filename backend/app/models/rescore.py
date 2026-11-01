import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base

class ImpactRescoringJob(Base):
    """
    Tracks bounded, idempotent guideline update impact re-scoring operations.
    Enforces ON DELETE RESTRICT against organization and knowledge-base versions,
    and supports soft archival.
    """
    __tablename__ = "impact_rescoring_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    knowledge_base_version_id = Column(String(36), nullable=False, index=True)
    idempotency_key = Column(String(64), nullable=False)
    status = Column(String(50), default="queued", nullable=False)  # queued, processing, completed, partially_failed, failed
    total_items = Column(Integer, default=0, nullable=False)
    completed_items = Column(Integer, default=0, nullable=False)
    failed_items = Column(Integer, default=0, nullable=False)
    total_batches = Column(Integer, default=0, nullable=False)
    completed_batches = Column(Integer, default=0, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", foreign_keys=[organization_id])
    knowledge_base_version = relationship("KnowledgeBaseVersion", foreign_keys=[knowledge_base_version_id])
    batch_items = relationship("ImpactRescoringBatchItem", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_impact_job_org_idempotency"),
        ForeignKeyConstraint(
            ["organization_id", "knowledge_base_version_id"],
            ["knowledge_base_versions.organization_id", "knowledge_base_versions.id"],
            name="fk_impact_jobs_kb",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'partially_failed', 'failed')",
            name="chk_impact_job_status",
        ),
    )


class ImpactRescoringBatchItem(Base):
    """
    Individual item evaluated within an impact re-scoring batch of 20.
    Stores immutable snapshot attributes (item ID, version number, checksum) so that
    historical audit records are preserved even if a content draft is later deleted or archived.
    Enforces ON DELETE RESTRICT on job_id and new_governance_run_id.
    """
    __tablename__ = "impact_rescoring_batch_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("impact_rescoring_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_index = Column(Integer, nullable=False)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    content_item_id = Column(String(36), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    content_checksum = Column(String(64), nullable=False)
    item_idempotency_key = Column(String(64), nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, completed, failed
    retry_count = Column(Integer, default=0, nullable=False)
    new_governance_run_id = Column(String(36), ForeignKey("governance_runs.id", ondelete="RESTRICT"), nullable=True)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)

    job = relationship("ImpactRescoringJob", back_populates="batch_items")
    content_version = relationship("ContentVersion", foreign_keys=[content_version_id])
    new_governance_run = relationship("GovernanceRun", foreign_keys=[new_governance_run_id])

    __table_args__ = (
        UniqueConstraint("job_id", "item_idempotency_key", name="uq_batch_item_idempotency"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="chk_batch_item_status",
        ),
    )
