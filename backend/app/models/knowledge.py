import uuid
from datetime import datetime, timedelta
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
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base

class KnowledgeSource(Base):
    """
    Source document or asset container uploaded by the organization.
    Critical: Uploading does NOT automatically approve contents. Status starts as pending_review.
    """
    __tablename__ = "knowledge_sources"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # pdf_brand_guidelines, pdf_product_knowledge, supporting_doc, brand_asset_image
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    mime_type = Column(String(100), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, reviewed, archived
    extracted_summary = Column(Text, nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="knowledge_sources")
    brand = relationship("Brand", back_populates="knowledge_sources")
    rules = relationship("KnowledgeRule", back_populates="source", cascade="all, delete-orphan")
    facts = relationship("KnowledgeFact", back_populates="source", cascade="all, delete-orphan")
    assets = relationship("BrandAsset", back_populates="source", cascade="all, delete-orphan")


class KnowledgeRule(Base):
    """
    Brand rules, prohibited wording, mandatory terms, tone guidelines.
    Only records with status='approved' are evaluated during governance checks.
    """
    __tablename__ = "knowledge_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    
    rule_type = Column(String(50), nullable=False)  # prohibited_word, required_term, tone_guideline, claim_policy, image_standard, asset_policy
    title = Column(String(255), nullable=False)
    pattern = Column(String(500), nullable=False)  # text pattern or keyword to check
    explanation = Column(Text, nullable=False)
    severity = Column(String(20), default="warning", nullable=False)  # critical, high, warning/medium, low, info
    context_condition = Column(String(255), nullable=True)  # optional context sensitive trigger
    scope = Column(String(255), default="all_channels", nullable=True)  # all_channels, social_posts, packaging, etc.
    source_citation = Column(String(255), nullable=True)  # e.g., "Brand Guidelines PDF, Section 3.1, p. 5"
    
    rule_code = Column(String(50), nullable=True, index=True)  # e.g. "FR-RULE-001"
    source_status = Column(String(50), default="unknown", nullable=True)  # approved, pending_review, expired, rejected
    enforcement_action = Column(String(50), default="flag_for_review", nullable=True)  # block, flag_for_review, escalate_to_human, warn
    rationale = Column(Text, nullable=True)
    recommended_alternatives = Column(Text, nullable=True)  # JSON or text list of preferred phrasing
    exceptions = Column(Text, nullable=True)  # JSON or text list of contextual exceptions
    examples_bad = Column(Text, nullable=True)  # JSON or text list of violation examples
    examples_good = Column(Text, nullable=True)  # JSON or text list of compliant examples
    evidence_passage = Column(Text, nullable=True)  # Exact supporting quotation
    page_number = Column(Integer, nullable=True)  # Primary source page
    evidence_validation = Column(String(50), default="unverified", nullable=True)  # verified_exact, verified_fuzzy, page_mismatch, unverified
    uncertainty_notes = Column(Text, nullable=True)  # Human review notes, ambiguity, data gaps
    original_extraction = Column(Text, nullable=True)  # JSON snapshot of machine extraction
    is_corrected = Column(Boolean, default=False, nullable=False)  # True if reviewer edited prior to approval

    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, approved, rejected, deprecated
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("KnowledgeSource", back_populates="rules")
    brand = relationship("Brand", back_populates="knowledge_rules")


class KnowledgeFact(Base):
    """
    Approved product knowledge, ingredients, nutritional values, claims, certifications.
    Only records with status='approved' (and within validity window) are authoritative.
    """
    __tablename__ = "knowledge_facts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    
    product_name = Column(String(255), nullable=False, index=True)  # e.g. "Freshsip Sparkling Citrus"
    category = Column(String(50), nullable=False)  # ingredient, nutrition, claim, certification, specification, pricing
    fact_key = Column(String(255), nullable=False)  # e.g. "sugar_content", "organic_certified", "caffeine"
    fact_value = Column(String(500), nullable=False)  # e.g. "0g added sugar", "USDA Organic", "45mg natural caffeine"
    
    product_id = Column(String(50), nullable=True, index=True)  # e.g. "FS-PROD-001"
    unit = Column(String(50), nullable=True)  # e.g. "mL", "g", "kcal", "%", "INR"
    value_status = Column(String(50), default="explicitly_stated", nullable=True)  # explicitly_stated, missing_not_provided, external_reference_needed
    source_status = Column(String(50), default="approved", nullable=True)  # approved, pending_review, expired, rejected
    page_number = Column(Integer, nullable=True)  # Primary source page
    evidence_validation = Column(String(50), default="unverified", nullable=True)  # verified_exact, verified_fuzzy, page_mismatch, unverified
    uncertainty_notes = Column(Text, nullable=True)  # Data gap or ambiguity notes
    original_extraction = Column(Text, nullable=True)  # JSON snapshot of machine extraction
    is_corrected = Column(Boolean, default=False, nullable=False)  # True if reviewer edited prior to approval

    supporting_evidence = Column(Text, nullable=True)
    source_citation = Column(String(255), nullable=True)  # e.g. "Product Knowledge PDF, p. 2"
    
    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, approved, rejected, expired
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("KnowledgeSource", back_populates="facts")
    brand = relationship("Brand", back_populates="knowledge_facts")


class BrandAsset(Base):
    """
    Brand assets: logos, campaign creatives, product images.
    Includes specs for image governance and product linkage.
    """
    __tablename__ = "brand_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    associated_product_id = Column(String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    
    asset_name = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False)  # logo, product_image, campaign_creative
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    aspect_ratio = Column(String(20), nullable=True)
    color_mode = Column(String(20), nullable=True)  # RGB, CMYK, etc.
    min_clearance_px = Column(Integer, default=20, nullable=True)
    alt_text_required = Column(Boolean, default=True, nullable=False)
    usage_notes = Column(Text, nullable=True)
    
    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, approved, rejected
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("KnowledgeSource", back_populates="assets")
    brand = relationship("Brand", back_populates="brand_assets")
    associated_product = relationship("Product", back_populates="brand_assets", foreign_keys=[associated_product_id])


class KnowledgeBaseVersion(Base):
    """
    Append-only immutable manifest of the complete organization brand governance knowledge base.
    Protected against UPDATE and DELETE by PostgreSQL database trigger trg_protect_kb_version_immutability.
    """
    __tablename__ = "knowledge_base_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    manifest_sha256 = Column(String(64), nullable=False)
    manifest_data = Column(JSON, nullable=False)
    activated_by = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    activated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activation_reason = Column(String(255), nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id])
    activator = relationship("User", foreign_keys=[activated_by])

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_kb_versions_org_id"),
        UniqueConstraint("organization_id", "version_num", name="uq_kb_versions_org_num"),
    )


class OrganizationActiveKnowledgeBase(Base):
    """
    Pointer table to the currently active immutable knowledge base version for each organization.
    Ensures knowledge_base_versions remains purely append-only without mutable status flags.
    """
    __tablename__ = "organization_active_knowledge_bases"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    active_version_id = Column(String(36), ForeignKey("knowledge_base_versions.id", ondelete="RESTRICT"), nullable=False)
    activated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    organization = relationship("Organization", foreign_keys=[organization_id])
    active_version = relationship("KnowledgeBaseVersion", foreign_keys=[active_version_id])


class StagedImport(Base):
    """
    Container for staged bulk Excel imports (Product Catalogue, Claims Register).
    Guarantees validation previews do not mutate active records and commits atomically.
    """
    __tablename__ = "staged_imports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    import_type = Column(String(50), nullable=False)  # product_catalogue, claims_and_disclosures
    idempotency_key = Column(String(64), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_sha256 = Column(String(64), nullable=False)
    status = Column(String(50), default="pending_preview", nullable=False)  # pending_preview, committed, failed, discarded
    total_rows = Column(Integer, default=0, nullable=False)
    valid_rows = Column(Integer, default=0, nullable=False)
    error_rows = Column(Integer, default=0, nullable=False)
    has_disclosures = Column(Boolean, default=False, nullable=False)
    validation_summary = Column(JSON, default=dict, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24), nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id])
    creator = relationship("User", foreign_keys=[created_by])
    staged_products = relationship("StagedImportProductRow", back_populates="import_session", cascade="all, delete-orphan")
    staged_claims = relationship("StagedImportClaimRow", back_populates="import_session", cascade="all, delete-orphan")
    staged_disclosures = relationship("StagedImportDisclosureRow", back_populates="import_session", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_staged_imports_org_id"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_staged_imports_org_idempotency"),
        CheckConstraint("import_type IN ('product_catalogue', 'claims_and_disclosures')", name="chk_staged_import_type"),
        CheckConstraint("status IN ('pending_preview', 'committed', 'failed', 'discarded')", name="chk_staged_import_status"),
    )


class StagedImportProductRow(Base):
    __tablename__ = "staged_import_product_rows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    import_id = Column(String(36), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    raw_data = Column(JSON, nullable=False)
    parsed_data = Column(JSON, nullable=True)
    validation_errors = Column(JSON, default=list, nullable=False)
    is_valid = Column(Boolean, default=False, nullable=False)

    import_session = relationship("StagedImport", back_populates="staged_products")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "import_id"],
            ["staged_imports.organization_id", "staged_imports.id"],
            name="fk_staged_products_import",
            ondelete="CASCADE",
        ),
    )


class StagedImportClaimRow(Base):
    __tablename__ = "staged_import_claim_rows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    import_id = Column(String(36), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    raw_data = Column(JSON, nullable=False)
    parsed_data = Column(JSON, nullable=True)
    validation_errors = Column(JSON, default=list, nullable=False)
    is_valid = Column(Boolean, default=False, nullable=False)

    import_session = relationship("StagedImport", back_populates="staged_claims")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "import_id"],
            ["staged_imports.organization_id", "staged_imports.id"],
            name="fk_staged_claims_import",
            ondelete="CASCADE",
        ),
    )


class StagedImportDisclosureRow(Base):
    __tablename__ = "staged_import_disclosure_rows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    import_id = Column(String(36), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    raw_data = Column(JSON, nullable=False)
    parsed_data = Column(JSON, nullable=True)
    validation_errors = Column(JSON, default=list, nullable=False)
    is_valid = Column(Boolean, default=False, nullable=False)

    import_session = relationship("StagedImport", back_populates="staged_disclosures")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "import_id"],
            ["staged_imports.organization_id", "staged_imports.id"],
            name="fk_staged_disclosures_import",
            ondelete="CASCADE",
        ),
    )
