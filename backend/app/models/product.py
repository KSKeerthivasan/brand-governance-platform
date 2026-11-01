import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class Product(Base):
    """
    Authoritative 15-column Product Catalogue offering model.
    Enforces tenant isolation via composite constraints and soft-deactivation (ON DELETE RESTRICT).
    """
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(String(100), nullable=False, index=True)  # Business SKU / Identifier e.g. FS-P001
    product_name = Column(String(255), nullable=False)
    product_category = Column(String(100), nullable=False)
    offering_type = Column(String(50), nullable=False)  # Physical Product, Service, Digital Product
    product_description = Column(Text, nullable=False)
    variant_name = Column(String(100), nullable=True)
    sku = Column(String(100), nullable=True)
    pack_size = Column(Numeric(10, 2), nullable=True)
    pack_unit = Column(String(50), nullable=True)
    ingredients_components = Column(Text, nullable=True)
    key_features = Column(Text, nullable=True)
    specifications = Column(Text, nullable=True)
    known_limitations = Column(Text, nullable=True)
    applicable_market = Column(String(100), nullable=False)
    record_status = Column(String(50), default="Active", nullable=False)  # Active, Inactive, Discontinued
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id])
    claims = relationship("Claim", back_populates="product", overlaps="claims")
    disclosures = relationship("RequiredDisclosure", back_populates="product", overlaps="disclosures")
    brand_assets = relationship("BrandAsset", back_populates="associated_product")
    content_items = relationship("ContentItem", back_populates="product", overlaps="content_items,product")

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_products_org_id"),
        UniqueConstraint("organization_id", "product_id", name="uq_products_org_business_id"),
        UniqueConstraint("organization_id", "id", "product_id", name="uq_products_org_id_business"),
        CheckConstraint("offering_type IN ('Physical Product', 'Service', 'Digital Product')", name="chk_product_offering_type"),
        CheckConstraint("record_status IN ('Active', 'Inactive', 'Discontinued')", name="chk_product_record_status"),
    )
