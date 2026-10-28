from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.schemas.governance import GovernanceFindingOut

class ApprovalSubmissionCreate(BaseModel):
    content_item_id: str
    content_version_id: str
    submission_notes: Optional[str] = None

class ApprovalDecisionCreate(BaseModel):
    decision: str  # approved, rejected, changes_requested
    comments: str

class ApprovalDecisionOut(BaseModel):
    id: str
    approval_submission_id: str
    content_version_id: str
    decided_by: str
    decider_name: Optional[str] = None
    decision: str
    decision_label: str
    comments: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ApprovalSubmissionOut(BaseModel):
    id: str
    content_item_id: str
    content_item_title: str
    channel: Optional[str] = "Social Media"
    brand_name: str
    content_version_id: str
    version_num: int
    body_text: str
    checksum: str
    submitted_by: str
    submitter_name: Optional[str] = None
    submission_notes: Optional[str] = None
    status: str
    created_at: datetime
    poster_file_path: Optional[str] = None
    poster_asset_id: Optional[str] = None
    poster_alt_text: Optional[str] = None
    poster_url: Optional[str] = None
    is_pdf: bool = False
    page_count: Optional[int] = None
    
    # Governance & Transparency Fields
    governance_run_id: Optional[str] = None
    governance_status: Optional[str] = None  # passed, warnings, failed
    rules_evaluated_count: int = 0
    facts_evaluated_count: int = 0
    findings_count: int = 0
    critical_findings_count: int = 0
    warning_findings_count: int = 0
    info_findings_count: int = 0
    findings: List[GovernanceFindingOut] = []
    
    decisions: List[ApprovalDecisionOut] = []

    model_config = ConfigDict(from_attributes=True)
