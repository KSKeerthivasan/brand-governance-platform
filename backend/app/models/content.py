import uuid
import hashlib
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class ContentItem(Base):
    """
    Marketing content draft container.
    """
    __tablename__ = "content_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(255), nullable=False)
    channel = Column(String(100), default="Social Media", nullable=False)  # Social Media, Email Newsletter, Web Banner, Print Ad
    current_version_num = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="draft", nullable=False)  # draft, submitted, approved, changes_requested, rejected
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="content_items")
    brand = relationship("Brand", back_populates="content_items")
    creator = relationship("User", back_populates="content_created")
    versions = relationship("ContentVersion", back_populates="content_item", cascade="all, delete-orphan", order_by="ContentVersion.version_num")
    submissions = relationship("ApprovalSubmission", back_populates="content_item", cascade="all, delete-orphan")


class ContentVersion(Base):
    """
    Immutable version snapshot of marketing content.
    Includes sha256 checksum to guarantee content identity.
    """
    __tablename__ = "content_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_item_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    body_text = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content_item = relationship("ContentItem", back_populates="versions")
    governance_runs = relationship("GovernanceRun", back_populates="content_version", cascade="all, delete-orphan")
    submissions = relationship("ApprovalSubmission", back_populates="content_version")
    decisions = relationship("ApprovalDecision", back_populates="content_version")

    __table_args__ = (
        UniqueConstraint("content_item_id", "version_num", name="uq_content_version_num"),
    )

    @staticmethod
    def calculate_checksum(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GovernanceRun(Base):
    """
    Execution record of the deterministic governance engine on a specific content version.
    """
    __tablename__ = "governance_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    executed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    overall_status = Column(String(50), nullable=False)  # passed, warnings, failed
    rules_evaluated_count = Column(Integer, default=0, nullable=False)
    facts_evaluated_count = Column(Integer, default=0, nullable=False)
    findings_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content_version = relationship("ContentVersion", back_populates="governance_runs")
    findings = relationship("GovernanceFinding", back_populates="governance_run", cascade="all, delete-orphan")


class GovernanceFinding(Base):
    """
    Explainable finding generated during a governance run.
    Must cite approved rules/facts or explicitly state evidence not found.
    """
    __tablename__ = "governance_findings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    governance_run_id = Column(String(36), ForeignKey("governance_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    category = Column(String(50), nullable=False)  
    # prohibited_wording, product_fact_mismatch, unsupported_claim, claim_status_issue, mandatory_wording_missing, source_freshness_issue, missing_evidence, image_guideline_issue
    
    severity = Column(String(20), nullable=False)  # critical, warning, info
    title = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=False)
    text_excerpt = Column(Text, nullable=True)
    
    matched_rule_id = Column(String(36), ForeignKey("knowledge_rules.id", ondelete="SET NULL"), nullable=True)
    matched_fact_id = Column(String(36), ForeignKey("knowledge_facts.id", ondelete="SET NULL"), nullable=True)
    
    source_citation = Column(String(255), nullable=False)  # Document citation or "SUPPORTING EVIDENCE NOT FOUND"
    recommended_action = Column(Text, nullable=False)
    status = Column(String(50), default="unresolved", nullable=False)  # unresolved, resolved, ignored
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    governance_run = relationship("GovernanceRun", back_populates="findings")
    matched_rule = relationship("KnowledgeRule")
    matched_fact = relationship("KnowledgeFact")


class ApprovalSubmission(Base):
    """
    Formal submission of an immutable content version for human approval.
    """
    __tablename__ = "approval_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_item_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    governance_run_id = Column(String(36), ForeignKey("governance_runs.id", ondelete="SET NULL"), nullable=True)
    submitted_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    submission_notes = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, approved, rejected, changes_requested
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content_item = relationship("ContentItem", back_populates="submissions")
    content_version = relationship("ContentVersion", back_populates="submissions")
    decisions = relationship("ApprovalDecision", back_populates="submission", cascade="all, delete-orphan")


class ApprovalDecision(Base):
    """
    Human review decision made by an authorized Approval Manager.
    Immutable record with actor, timestamp, comments, and exact version.
    """
    __tablename__ = "approval_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    approval_submission_id = Column(String(36), ForeignKey("approval_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    decided_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    decision = Column(String(50), nullable=False)  # approved, rejected, changes_requested
    decision_label = Column(String(100), nullable=False)  # e.g., "Approved — Ready to Publish"
    comments = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    submission = relationship("ApprovalSubmission", back_populates="decisions")
    content_version = relationship("ContentVersion", back_populates="decisions")
    decider = relationship("User")
