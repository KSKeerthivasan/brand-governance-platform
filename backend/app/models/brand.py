import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base

class Brand(Base):
    __tablename__ = "brands"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="brands")
    knowledge_sources = relationship("KnowledgeSource", back_populates="brand")
    knowledge_rules = relationship("KnowledgeRule", back_populates="brand")
    knowledge_facts = relationship("KnowledgeFact", back_populates="brand")
    brand_assets = relationship("BrandAsset", back_populates="brand")
    content_items = relationship("ContentItem", back_populates="brand")


class BrandProfile(Base):
    """
    Authoritative Brand Guidelines Model (Input 1 - Sections A, B, D, E).
    Source of truth for brand identity, voice, typography, and visual rules.
    """
    __tablename__ = "brand_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Section A: Brand Identity
    brand_name = Column(String(255), nullable=False)
    brand_description = Column(Text, nullable=False)
    approved_taglines = Column(JSON, nullable=False, default=list)

    # Section B: Voice & Communication
    brand_personality = Column(JSON, nullable=False, default=list)
    preferred_tone = Column(JSON, nullable=False, default=list)
    tones_to_avoid = Column(JSON, nullable=False, default=list)
    preferred_terminology = Column(JSON, nullable=False, default=list)
    prohibited_terminology = Column(JSON, nullable=False, default=list)
    writing_style = Column(String(100), nullable=False)
    approved_languages = Column(JSON, nullable=False, default=lambda: ["en"])

    # Section D: Typography
    primary_heading_font = Column(String(100), nullable=False)
    secondary_body_font = Column(String(100), nullable=False)
    additional_approved_fonts = Column(JSON, nullable=False, default=list)
    typography_instructions = Column(Text, nullable=True)

    # Section E: Visual Identity Rules
    visual_style = Column(JSON, nullable=False, default=list)
    preferred_imagery_style = Column(JSON, nullable=False, default=list)
    preferred_backgrounds = Column(JSON, nullable=False, default=list)
    visual_styles_to_avoid = Column(JSON, nullable=False, default=list)
    logo_usage_instructions = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id])
    colors = relationship("BrandColor", back_populates="brand_profile", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_brand_profiles_org"),
    )


class BrandColor(Base):
    """
    Authoritative Brand Colour Palette Model (Input 1 - Section C).
    Enforces multi-color palettes with exact HEX and RGB channel bounds.
    """
    __tablename__ = "brand_colors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), nullable=False, index=True)
    brand_profile_id = Column(String(36), nullable=False, index=True)

    colour_name = Column(String(100), nullable=False)
    colour_family = Column(String(50), nullable=False)
    colour_role = Column(String(50), nullable=False)  # Primary, Secondary, Accent, Background, Text, Neutral
    hex_value = Column(String(7), nullable=False)
    rgb_r = Column(Integer, nullable=False)
    rgb_g = Column(Integer, nullable=False)
    rgb_b = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    brand_profile = relationship("BrandProfile", back_populates="colors")

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "brand_profile_id"],
            ["brand_profiles.organization_id", "brand_profiles.id"],
            name="fk_brand_colors_org_profile",
            ondelete="CASCADE",
        ),
        CheckConstraint("rgb_r BETWEEN 0 AND 255", name="chk_color_rgb_r"),
        CheckConstraint("rgb_g BETWEEN 0 AND 255", name="chk_color_rgb_g"),
        CheckConstraint("rgb_b BETWEEN 0 AND 255", name="chk_color_rgb_b"),
    )
