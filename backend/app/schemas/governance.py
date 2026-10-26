from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class GovernanceFindingOut(BaseModel):
    id: str
    governance_run_id: str
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

    model_config = ConfigDict(from_attributes=True)

class GovernanceRunRequest(BaseModel):
    content_version_id: str

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
