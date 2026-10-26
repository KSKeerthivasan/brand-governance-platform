import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
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
