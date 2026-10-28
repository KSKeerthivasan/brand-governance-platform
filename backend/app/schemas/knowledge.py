from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class KnowledgeRuleBase(BaseModel):
    rule_type: str  # prohibited_word, required_term, tone_guideline, claim_policy, image_standard, asset_policy
    title: str
    pattern: str
    explanation: str
    severity: str = "warning"
    context_condition: Optional[str] = None
    scope: Optional[str] = "all_channels"
    source_citation: Optional[str] = None
    
    # Extended Stage 2 Metadata
    rule_code: Optional[str] = None
    source_status: Optional[str] = "unknown"  # approved, pending_review, expired, rejected
    enforcement_action: Optional[str] = "flag_for_review"
    rationale: Optional[str] = None
    recommended_alternatives: Optional[str] = None
    exceptions: Optional[str] = None
    examples_bad: Optional[str] = None
    examples_good: Optional[str] = None
    evidence_passage: Optional[str] = None
    page_number: Optional[int] = None
    evidence_validation: Optional[str] = "unverified"
    uncertainty_notes: Optional[str] = None
    original_extraction: Optional[str] = None
    is_corrected: bool = False

class KnowledgeRuleCreate(KnowledgeRuleBase):
    brand_id: Optional[str] = None
    source_id: Optional[str] = None

class KnowledgeRuleUpdate(BaseModel):
    title: Optional[str] = None
    pattern: Optional[str] = None
    explanation: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    rule_type: Optional[str] = None
    context_condition: Optional[str] = None
    recommended_alternatives: Optional[str] = None
    exceptions: Optional[str] = None
    review_notes: Optional[str] = None

class KnowledgeRuleReview(BaseModel):
    status: str  # approved, rejected, deprecated
    review_notes: Optional[str] = None
    corrected_title: Optional[str] = None
    corrected_pattern: Optional[str] = None
    corrected_explanation: Optional[str] = None

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

    model_config = ConfigDict(from_attributes=True)

class KnowledgeFactBase(BaseModel):
    product_name: str
    category: str  # ingredient, nutrition, claim, certification, specification, pricing
    fact_key: str
    fact_value: str
    supporting_evidence: Optional[str] = None
    source_citation: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    # Extended Stage 2 Metadata
    product_id: Optional[str] = None
    unit: Optional[str] = None
    value_status: Optional[str] = "explicitly_stated"
    source_status: Optional[str] = "approved"
    page_number: Optional[int] = None
    evidence_validation: Optional[str] = "unverified"
    uncertainty_notes: Optional[str] = None
    original_extraction: Optional[str] = None
    is_corrected: bool = False

class KnowledgeFactCreate(KnowledgeFactBase):
    brand_id: Optional[str] = None
    source_id: Optional[str] = None

class KnowledgeFactUpdate(BaseModel):
    product_name: Optional[str] = None
    category: Optional[str] = None
    fact_key: Optional[str] = None
    fact_value: Optional[str] = None
    supporting_evidence: Optional[str] = None
    unit: Optional[str] = None
    review_notes: Optional[str] = None

class KnowledgeFactReview(BaseModel):
    status: str  # approved, rejected, expired
    review_notes: Optional[str] = None
    corrected_fact_key: Optional[str] = None
    corrected_fact_value: Optional[str] = None

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)
