from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class KnowledgeRuleBase(BaseModel):
    rule_type: str  # prohibited_word, required_term, tone_guideline, claim_policy, image_standard
    title: str
    pattern: str
    explanation: str
    severity: str = "warning"
    context_condition: Optional[str] = None
    source_citation: Optional[str] = None

class KnowledgeRuleCreate(KnowledgeRuleBase):
    brand_id: Optional[str] = None
    source_id: Optional[str] = None

class KnowledgeRuleReview(BaseModel):
    status: str  # approved, rejected, deprecated
    review_notes: Optional[str] = None

class KnowledgeRuleOut(KnowledgeRuleBase):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeFactBase(BaseModel):
    product_name: str
    category: str  # ingredient, nutrition, claim, certification, specification, pricing
    fact_key: str
    fact_value: str
    supporting_evidence: Optional[str] = None
    source_citation: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

class KnowledgeFactCreate(KnowledgeFactBase):
    brand_id: Optional[str] = None
    source_id: Optional[str] = None

class KnowledgeFactReview(BaseModel):
    status: str  # approved, rejected, expired
    review_notes: Optional[str] = None

class KnowledgeFactOut(KnowledgeFactBase):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class BrandAssetBase(BaseModel):
    asset_name: str
    asset_type: str
    file_path: str
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[str] = None
    color_mode: Optional[str] = None
    min_clearance_px: Optional[int] = 20
    alt_text_required: bool = True

class BrandAssetReview(BaseModel):
    status: str  # approved, rejected

class BrandAssetOut(BrandAssetBase):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeSourceOut(BaseModel):
    id: str
    organization_id: str
    brand_id: Optional[str] = None
    title: str
    source_type: str
    filename: str
    file_size_bytes: int
    mime_type: str
    version: int
    status: str
    extracted_summary: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    rules_count: Optional[int] = 0
    facts_count: Optional[int] = 0
    assets_count: Optional[int] = 0

    class Config:
        from_attributes = True
