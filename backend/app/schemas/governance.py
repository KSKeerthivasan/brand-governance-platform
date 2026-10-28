from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CorrectionSuggestionOut(BaseModel):
    id: str
    finding_id: str
    content_item_id: str
    content_version_id: str
    source_checksum: str
    target_type: str  # body_text, poster_image, pdf_page
    page_number: Optional[int] = None
    rule_id: Optional[str] = None
    rule_code: Optional[str] = None
    fact_id: Optional[str] = None
    fact_key: Optional[str] = None
    original_text: str
    proposed_text: Optional[str] = None
    diff_preview: Optional[str] = None
    explanation: str
    evidence_source: str
    correction_type: str
    confidence: str
    can_auto_apply: bool
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CorrectionSuggestionApplyResponse(BaseModel):
    suggestion: CorrectionSuggestionOut
    content_item_id: str
    new_version_num: Optional[int] = None
    new_version_id: Optional[str] = None
    applied_to_text: bool
    message: str

class CorrectionSuggestionCustomApplyRequest(BaseModel):
    custom_text: str

class GovernanceFindingOut(BaseModel):
    id: str
    governance_run_id: str
    page_number: Optional[int] = None
    category: str
    severity: str
    title: str
    explanation: str
    text_excerpt: Optional[str] = None
    matched_rule_id: Optional[str] = None
    matched_fact_id: Optional[str] = None
    source_citation: str
    recommended_action: str
    status: str
    created_at: datetime
    suggestion: Optional[CorrectionSuggestionOut] = None

    model_config = ConfigDict(from_attributes=True)

class GovernanceRunRequest(BaseModel):
    content_version_id: str
    product_id: Optional[str] = None

class GovernanceRunOut(BaseModel):
    id: str
    content_version_id: str
    executed_by: Optional[str] = None
    overall_status: str
    rules_evaluated_count: int
    facts_evaluated_count: int
    findings_count: int
    created_at: datetime
    findings: List[GovernanceFindingOut] = []

    model_config = ConfigDict(from_attributes=True)

class ImageGovernanceCheckRequest(BaseModel):
    asset_id: Optional[str] = None
    image_url: Optional[str] = None
    channel: str = "Social Media"
    alt_text: Optional[str] = None

class ImageGovernanceCheckResult(BaseModel):
    passed: bool
    dimensions: Optional[str] = None
    aspect_ratio: Optional[str] = None
    color_mode: Optional[str] = None
    findings: List[str] = []
    recommendations: List[str] = []
