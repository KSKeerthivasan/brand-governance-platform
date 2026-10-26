from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

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

    class Config:
        from_attributes = True

class ApprovalSubmissionOut(BaseModel):
    id: str
    content_item_id: str
    content_item_title: str
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
    decisions: List[ApprovalDecisionOut] = []

    class Config:
        from_attributes = True
