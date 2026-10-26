import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index
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
    
    rule_type = Column(String(50), nullable=False)  # prohibited_word, required_term, tone_guideline, claim_policy, image_standard
    title = Column(String(255), nullable=False)
    pattern = Column(String(500), nullable=False)  # text pattern or keyword to check
    explanation = Column(Text, nullable=False)
    severity = Column(String(20), default="warning", nullable=False)  # critical, warning, info
    context_condition = Column(String(255), nullable=True)  # optional context sensitive trigger
    source_citation = Column(String(255), nullable=True)  # e.g., "Brand Guidelines PDF, Section 3.1, p. 5"
    
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
    Includes specs for image governance (Round 3 Improvement 3).
    """
    __tablename__ = "brand_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    
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
    
    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, approved, rejected
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("KnowledgeSource", back_populates="assets")
    brand = relationship("Brand", back_populates="brand_assets")
