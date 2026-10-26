from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.content import (
    ContentItem, ContentVersion, GovernanceRun,
    ApprovalSubmission, ApprovalDecision
)
from app.models.brand import Brand
from app.schemas.approval import (
    ApprovalSubmissionCreate, ApprovalSubmissionOut,
    ApprovalDecisionCreate, ApprovalDecisionOut
)
from app.api.deps import (
    get_current_user, require_any_member,
    require_content_creator, require_approval_manager
)
from app.services.audit import log_audit_event

router = APIRouter()

@router.post("/submit", response_model=ApprovalSubmissionOut)
def submit_content_for_approval(
    req: ApprovalSubmissionCreate,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 8: Submit a specific immutable content version for human approval.
    """
    version = db.query(ContentVersion).filter(ContentVersion.id == req.content_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Content version not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == req.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Content draft not found.")

    # Check latest governance run
    latest_run = db.query(GovernanceRun).filter(
        GovernanceRun.content_version_id == version.id
    ).order_by(GovernanceRun.created_at.desc()).first()

    submission = ApprovalSubmission(
        content_item_id=item.id,
        content_version_id=version.id,
        governance_run_id=latest_run.id if latest_run else None,
        submitted_by=current_user.id,
        submission_notes=req.submission_notes,
        status="pending"
    )
    db.add(submission)

    # Transition content item state to submitted
    item.status = "submitted"
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(submission)

    brand = db.query(Brand).filter(Brand.id == item.brand_id).first()

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="APPROVAL_SUBMITTED",
        entity_type="approval_submission",
        entity_id=submission.id,
        summary=f"Submitted '{item.title}' v{version.version_num} for approval",
        details={
            "version_num": version.version_num,
            "checksum": version.checksum,
            "notes": req.submission_notes
        }
    )

    return ApprovalSubmissionOut(
        id=submission.id,
        content_item_id=item.id,
        content_item_title=item.title,
        brand_name=brand.name if brand else "Brand",
        content_version_id=version.id,
        version_num=version.version_num,
        body_text=version.body_text,
        checksum=version.checksum,
        submitted_by=current_user.id,
        submitter_name=current_user.full_name,
        submission_notes=submission.submission_notes,
        status=submission.status,
        created_at=submission.created_at,
        decisions=[]
    )


@router.get("/queue", response_model=List[ApprovalSubmissionOut])
def list_approval_queue(
    status_filter: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    List submissions in the approval queue for this organization.
    """
    query = db.query(ApprovalSubmission).join(
        ContentItem, ContentItem.id == ApprovalSubmission.content_item_id
    ).filter(
        ContentItem.organization_id == membership.organization_id
    )

    if status_filter:
        query = query.filter(ApprovalSubmission.status == status_filter)

    submissions = query.order_by(ApprovalSubmission.created_at.desc()).all()

    result = []
    for s in submissions:
        item = db.query(ContentItem).filter(ContentItem.id == s.content_item_id).first()
        brand = db.query(Brand).filter(Brand.id == item.brand_id).first() if item else None
        version = db.query(ContentVersion).filter(ContentVersion.id == s.content_version_id).first()
        submitter = db.query(User).filter(User.id == s.submitted_by).first()

        decisions = db.query(ApprovalDecision).filter(
            ApprovalDecision.approval_submission_id == s.id
        ).order_by(ApprovalDecision.created_at.desc()).all()

        dec_list = []
        for d in decisions:
            decider = db.query(User).filter(User.id == d.decided_by).first()
            dec_list.append(ApprovalDecisionOut(
                id=d.id,
                approval_submission_id=d.approval_submission_id,
                content_version_id=d.content_version_id,
                decided_by=d.decided_by,
                decider_name=decider.full_name if decider else "Manager",
                decision=d.decision,
                decision_label=d.decision_label,
                comments=d.comments,
                created_at=d.created_at
            ))

        result.append(ApprovalSubmissionOut(
            id=s.id,
            content_item_id=s.content_item_id,
            content_item_title=item.title if item else "Unknown",
            brand_name=brand.name if brand else "Brand",
            content_version_id=s.content_version_id,
            version_num=version.version_num if version else 1,
            body_text=version.body_text if version else "",
            checksum=version.checksum if version else "",
            submitted_by=s.submitted_by,
            submitter_name=submitter.full_name if submitter else "Creator",
            submission_notes=s.submission_notes,
            status=s.status,
            created_at=s.created_at,
            decisions=dec_list
        ))

    return result


@router.post("/submissions/{submission_id}/decide", response_model=ApprovalDecisionOut)
def record_approval_decision(
    submission_id: str,
    req: ApprovalDecisionCreate,
    membership: OrganizationMembership = Depends(require_approval_manager),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 8: Human approval decision by authorized Approval Manager.
    - Creator cannot approve their own content.
    - Locks decision to the exact submitted version.
    - Uses official label: 'Approved — Ready to Publish' on approval.
    """
    submission = db.query(ApprovalSubmission).filter(
        ApprovalSubmission.id == submission_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Approval submission not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == submission.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Submission does not belong to your organization.")

    # Critical Security Invariant: Creator CANNOT approve their own content!
    if submission.submitted_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conflict of Interest: Content creators cannot approve their own content submissions."
        )

    if req.decision not in ["approved", "rejected", "changes_requested"]:
        raise HTTPException(status_code=400, detail="Decision must be 'approved', 'rejected', or 'changes_requested'.")

    # Format official final status label
    decision_label = "Approved — Ready to Publish" if req.decision == "approved" else (
        "Changes Requested" if req.decision == "changes_requested" else "Rejected"
    )

    decision_obj = ApprovalDecision(
        approval_submission_id=submission.id,
        content_version_id=submission.content_version_id,
        decided_by=current_user.id,
        decision=req.decision,
        decision_label=decision_label,
        comments=req.comments
    )
    db.add(decision_obj)

    # Update submission status
    submission.status = req.decision

    # Update content item status
    item.status = req.decision
    item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(decision_obj)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type=f"APPROVAL_{req.decision.upper()}",
        entity_type="approval_decision",
        entity_id=decision_obj.id,
        summary=f"Approval Manager decided: {decision_label} for '{item.title}' v{submission.content_version.version_num}",
        details={
            "content_version_id": submission.content_version_id,
            "decision": req.decision,
            "comments": req.comments
        }
    )

    return ApprovalDecisionOut(
        id=decision_obj.id,
        approval_submission_id=decision_obj.approval_submission_id,
        content_version_id=decision_obj.content_version_id,
        decided_by=decision_obj.decided_by,
        decider_name=current_user.full_name,
        decision=decision_obj.decision,
        decision_label=decision_obj.decision_label,
        comments=decision_obj.comments,
        created_at=decision_obj.created_at
    )
