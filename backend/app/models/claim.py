import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base

class Claim(Base):
    """
    Authoritative 11-column Claims Register model.
    Enforces independent organization foreign key, 3-column composite product foreign key,
    and applicability integrity (ALL vs specific SKU).
    """
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(String(36), nullable=True, index=True)  # NULL when applicable_product_id = 'ALL'
    claim_id = Column(String(100), nullable=False, index=True)  # Business Claim ID e.g. CLM001
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(50), nullable=False)
    claim_status = Column(String(50), nullable=False)  # Approved, Restricted, Prohibited
    applicable_product_id = Column(String(100), nullable=False)  # Catalogue product_id or 'ALL'
    approved_variations = Column(Text, nullable=True)
    restricted_conditions = Column(Text, nullable=True)
    prohibited_variations = Column(Text, nullable=True)
    applicable_market = Column(String(100), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id], overlaps="claims")
    product = relationship("Product", back_populates="claims", foreign_keys=[product_id])

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_claims_org_id"),
        UniqueConstraint("organization_id", "claim_id", name="uq_claims_org_business_id"),
        ForeignKeyConstraint(
            ["organization_id", "product_id", "applicable_product_id"],
            ["products.organization_id", "products.id", "products.product_id"],
            name="fk_claims_org_product_sku",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(applicable_product_id = 'ALL' AND product_id IS NULL) OR (applicable_product_id <> 'ALL' AND product_id IS NOT NULL)",
            name="chk_claim_product_applicability",
        ),
        CheckConstraint(
            "claim_status IN ('Approved', 'Restricted', 'Prohibited')",
            name="chk_claim_status",
        ),
        CheckConstraint(
            "(claim_status <> 'Restricted') OR (restricted_conditions IS NOT NULL AND length(trim(restricted_conditions)) > 0)",
            name="chk_claim_restricted_condition",
        ),
        CheckConstraint(
            "length(trim(claim_type)) > 0",
            name="chk_claim_type_not_empty",
        ),
    )


class RequiredDisclosure(Base):
    """
    Authoritative 7-column Required Disclosures model (optional worksheet).
    Enforces atomic commit alongside Claims Register and tenant/product applicability.
    """
    __tablename__ = "required_disclosures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(String(36), nullable=True, index=True)  # NULL when applicable_product_id = 'ALL'
    disclosure_id = Column(String(100), nullable=False, index=True)  # e.g. DISC001
    disclosure_text = Column(Text, nullable=False)
    applicable_product_id = Column(String(100), nullable=False)
    applicable_market = Column(String(100), nullable=False)
    applies_when = Column(Text, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id], overlaps="disclosures")
    product = relationship("Product", back_populates="disclosures", foreign_keys=[product_id])

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_disclosures_org_id"),
        UniqueConstraint("organization_id", "disclosure_id", name="uq_disclosures_org_business_id"),
        ForeignKeyConstraint(
            ["organization_id", "product_id", "applicable_product_id"],
            ["products.organization_id", "products.id", "products.product_id"],
            name="fk_disclosures_org_product_sku",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(applicable_product_id = 'ALL' AND product_id IS NULL) OR (applicable_product_id <> 'ALL' AND product_id IS NOT NULL)",
            name="chk_disclosure_product_applicability",
        ),
    )
