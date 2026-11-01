import uuid
from datetime import datetime, timedelta
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan")
    brands = relationship("Brand", back_populates="organization", cascade="all, delete-orphan")
    knowledge_sources = relationship("KnowledgeSource", back_populates="organization", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
    invitations = relationship("OrganizationInvitation", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    memberships = relationship("OrganizationMembership", back_populates="user", cascade="all, delete-orphan")
    content_created = relationship("ContentItem", back_populates="creator")
    revoked_tokens = relationship("RevokedToken", back_populates="user", cascade="all, delete-orphan")


class OrganizationRole:
    ORG_ADMIN = "org_admin"
    KNOWLEDGE_REVIEWER = "knowledge_reviewer"
    CONTENT_CREATOR = "content_creator"
    APPROVAL_MANAGER = "approval_manager"
    ALL_ROLES = [ORG_ADMIN, KNOWLEDGE_REVIEWER, CONTENT_CREATOR, APPROVAL_MANAGER]


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # OrganizationRole
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jti = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    reason = Column(String(100), nullable=True)

    user = relationship("User", back_populates="revoked_tokens")


class OrganizationInvitation(Base):
    """
    Secure invitation model for workspace team onboarding.
    Supports email normalization, single pending invitation constraint,
    inviter audit preservation, and single-use token consumption.
    """
    __tablename__ = "organization_invitations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email_normalized = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # OrganizationRole
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    delivery_method = Column(String(50), default="firebase_email_link", nullable=False)
    delivery_status = Column(String(50), default="pending", nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, accepted, expired, revoked
    invited_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    inviter_email_snapshot = Column(String(255), nullable=False)
    accepted_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=7), nullable=False)
    consumed_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[invited_by])
    accepted_by = relationship("User", foreign_keys=[accepted_by_user_id])

    __table_args__ = (
        CheckConstraint(
            "role IN ('org_admin', 'knowledge_reviewer', 'content_creator', 'approval_manager')",
            name="chk_invitation_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="chk_invitation_status",
        ),
        Index(
            "idx_single_pending_invitation",
            "organization_id",
            "email_normalized",
            unique=True,
            postgresql_where=Column("status") == "pending",
        ),
    )
