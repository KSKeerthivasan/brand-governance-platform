from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.content import (
    ContentItem, ContentVersion, GovernanceRun, GovernanceFinding,
    ApprovalSubmission, ApprovalDecision
)
from app.models.brand import Brand
from app.schemas.approval import (
    ApprovalSubmissionCreate, ApprovalSubmissionOut,
    ApprovalDecisionCreate, ApprovalDecisionOut
)
from app.schemas.governance import GovernanceFindingOut
from app.api.deps import (
    get_current_user, require_any_member,
    require_content_creator, require_approval_manager
)
from app.services.audit import log_audit_event

router = APIRouter()

def _build_submission_out(s: ApprovalSubmission, db: Session) -> ApprovalSubmissionOut:
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

    gov_run = None
    if s.governance_run_id:
        gov_run = db.query(GovernanceRun).filter(GovernanceRun.id == s.governance_run_id).first()
    if not gov_run and version:
        gov_run = db.query(GovernanceRun).filter(
            GovernanceRun.content_version_id == version.id
        ).order_by(GovernanceRun.created_at.desc()).first()

    findings_out: List[GovernanceFindingOut] = []
    crit_count = 0
    warn_count = 0
    info_count = 0
    gov_status = None
    rules_count = 0
    facts_count = 0
    findings_count = 0

    if gov_run:
        gov_status = gov_run.overall_status
        rules_count = gov_run.rules_evaluated_count
        facts_count = gov_run.facts_evaluated_count
        findings_count = gov_run.findings_count
        f_records = db.query(GovernanceFinding).filter(GovernanceFinding.governance_run_id == gov_run.id).all()
        for f in f_records:
            if f.severity in ("critical", "high"):
                crit_count += 1
            elif f.severity == "warning":
                warn_count += 1
            else:
                info_count += 1
            findings_out.append(GovernanceFindingOut.model_validate(f))

    return ApprovalSubmissionOut(
        id=s.id,
        content_item_id=s.content_item_id,
        content_item_title=item.title if item else "Unknown",
        channel=item.channel if item else "Social Media",
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
        poster_file_path=version.poster_file_path if version else None,
        poster_asset_id=version.poster_asset_id if version else None,
        poster_alt_text=version.poster_alt_text if version else None,
        poster_url=f"/api/v1/content/versions/{version.id}/poster" if (version and version.poster_file_path) else None,
        is_pdf=bool(version and version.poster_file_path and version.poster_file_path.lower().endswith(".pdf")),
        page_count=(
            (lambda p: (
                (lambda: (
                    __import__('app.services.pdf_service', fromlist=['pdf_service']).pdf_service.validate_pdf_file(p).page_count
                    if __import__('os').path.exists(p) else None
                ))()
            ))(version.poster_file_path)
            if (version and version.poster_file_path and version.poster_file_path.lower().endswith(".pdf"))
            else None
        ),
        governance_run_id=gov_run.id if gov_run else None,
        governance_status=gov_status,
        rules_evaluated_count=rules_count,
        facts_evaluated_count=facts_count,
        findings_count=findings_count,
        critical_findings_count=crit_count,
        warning_findings_count=warn_count,
        info_findings_count=info_count,
        findings=findings_out,
        decisions=dec_list
    )


@router.post("/submit", response_model=ApprovalSubmissionOut)
def submit_content_for_approval(
    req: ApprovalSubmissionCreate,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 8: Fail-closed submission of an immutable content version for human approval.
    Enforces strict preconditions:
      1. Content version and draft item exist and belong to the user's organization.
      2. Content version must match current draft version (rejects stale/obsolete versions).
      3. Content and attached poster checksum on disk must match the version's immutable checksum.
      4. A completed governance run must exist for this exact version.
      5. Governance run must belong to this version (run for an old version cannot authorize a newer version).
      6. No unresolved critical/high policy violations may exist (fail-closed on critical claims).
      7. Overall governance status cannot be 'failed'.
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

    if version.content_item_id != item.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version Mismatch: Specified content version does not belong to this content draft."
        )

    # Precondition 1: Version staleness (reject submitting an older version if draft was revised)
    if version.version_num != item.current_version_num:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stale Version: Cannot submit obsolete version v{version.version_num}. Current draft version is v{item.current_version_num}."
        )

    # Precondition 2: Content & Asset Checksum Integrity
    current_checksum = ContentVersion.calculate_checksum(version.body_text, version.poster_file_path)
    if current_checksum != version.checksum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity Checksum Mismatch: Content body or attached asset has changed on disk since version creation. Please save and re-run governance."
        )

    # Precondition 3: Governance Run Exists for THIS exact version
    latest_run = db.query(GovernanceRun).filter(
        GovernanceRun.content_version_id == version.id
    ).order_by(GovernanceRun.created_at.desc()).first()

    if not latest_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Submission Rejected: No completed governance run exists for content version v{version.version_num}. You must execute governance checks before submitting for approval."
        )

    # Precondition 4: Governance Run Must Belong to Current Version
    if latest_run.content_version_id != version.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Governance Version Mismatch: Latest governance run belongs to another version, not submitted version v{version.version_num}."
        )

    # Precondition 5: Check for Critical Blocking Findings & Fail-Closed Status
    findings = db.query(GovernanceFinding).filter(
        GovernanceFinding.governance_run_id == latest_run.id
    ).all()

    critical_blockers = [
        f for f in findings
        if f.severity in ("critical", "high") and f.status != "passed_check"
    ]
    if critical_blockers:
        blocker_titles = "; ".join([f.title for f in critical_blockers[:3]])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Submission Rejected: Content version v{version.version_num} contains {len(critical_blockers)} "
                f"unresolved blocking violation(s) ({blocker_titles}). All critical policy violations must be resolved before submission."
            )
        )

    if latest_run.overall_status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission Rejected: Governance run failed. Content cannot be submitted while governance status is 'failed'."
        )

    # Create submission bound to the exact version and governance run
    submission = ApprovalSubmission(
        content_item_id=item.id,
        content_version_id=version.id,
        governance_run_id=latest_run.id,
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

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="APPROVAL_SUBMITTED",
        entity_type="approval_submission",
        entity_id=submission.id,
        summary=f"Submitted '{item.title}' v{version.version_num} for approval (governance status: {latest_run.overall_status.upper()})",
        details={
            "version_num": version.version_num,
            "checksum": version.checksum,
            "governance_run_id": latest_run.id,
            "governance_status": latest_run.overall_status,
            "findings_count": len(findings),
            "notes": req.submission_notes
        }
    )

    return _build_submission_out(submission, db)


@router.get("/queue", response_model=List[ApprovalSubmissionOut])
def list_approval_queue(
    status_filter: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    List submissions in the approval queue for this organization with full findings transparency.
    """
    query = db.query(ApprovalSubmission).join(
        ContentItem, ContentItem.id == ApprovalSubmission.content_item_id
    ).filter(
        ContentItem.organization_id == membership.organization_id
    )

    if status_filter:
        query = query.filter(ApprovalSubmission.status == status_filter)

    submissions = query.order_by(ApprovalSubmission.created_at.desc()).all()
    return [_build_submission_out(s, db) for s in submissions]


@router.get("/submissions/{submission_id}", response_model=ApprovalSubmissionOut)
def get_approval_submission(
    submission_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Fetch a single approval submission with complete versioned findings and evidence.
    """
    submission = db.query(ApprovalSubmission).filter(ApprovalSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Approval submission not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == submission.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()
    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Submission does not belong to your organization.")

    return _build_submission_out(submission, db)


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
    Enforces strict invariants:
      1. Role: Only Approval Managers may record decisions.
      2. Tenant isolation: Submission must belong to user's organization.
      3. Conflict of Interest: Creators cannot approve their own submissions.
      4. Version Integrity: Submission version must match current draft version (rejects stale submissions).
      5. Checksum Integrity: Body and asset checksum must match submitted version snapshot.
      6. Policy Gate: Critical violations cannot be approved through ordinary override.
      7. Justification Gate: Warning overrides require substantive explanation (minimum 10 chars).
      8. Rejection / Changes Requested require recorded comments.
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

    # Invariant: Creator CANNOT approve their own content
    if submission.submitted_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conflict of Interest: Content creators cannot approve their own content submissions."
        )

    if req.decision not in ["approved", "rejected", "changes_requested"]:
        raise HTTPException(status_code=400, detail="Decision must be 'approved', 'rejected', or 'changes_requested'.")

    # Invariant: Submissions for obsolete versions cannot be approved
    version = submission.content_version
    if version.version_num != item.current_version_num:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stale Submission: Content has been revised to version v{item.current_version_num}. Approval cannot be granted for obsolete version v{version.version_num}."
        )

    # Invariant: Checksum verification at decision time
    current_checksum = ContentVersion.calculate_checksum(version.body_text, version.poster_file_path)
    if current_checksum != version.checksum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity Checksum Mismatch: Content body or attached asset has been modified since submission."
        )

    # Query governance findings for this submission
    latest_run = None
    if submission.governance_run_id:
        latest_run = db.query(GovernanceRun).filter(GovernanceRun.id == submission.governance_run_id).first()
    if not latest_run:
        latest_run = db.query(GovernanceRun).filter(
            GovernanceRun.content_version_id == version.id
        ).order_by(GovernanceRun.created_at.desc()).first()

    findings = []
    if latest_run:
        findings = db.query(GovernanceFinding).filter(GovernanceFinding.governance_run_id == latest_run.id).all()

    critical_blockers = [
        f for f in findings
        if f.severity in ("critical", "high") and f.status != "passed_check"
    ]
    warnings = [
        f for f in findings
        if f.severity == "warning" and f.status != "passed_check"
    ]

    # Invariant: Critical prohibited claims cannot be approved under any override
    if req.decision == "approved":
        if critical_blockers:
            blocker_titles = "; ".join([f.title for f in critical_blockers[:3]])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval Denied: Cannot approve content with {len(critical_blockers)} unresolved critical violation(s) ({blocker_titles}). Critical policy prohibitions cannot be overridden."
            )

        # Invariant: Warning overrides require recorded justification
        if warnings:
            if not req.comments or len(req.comments.strip()) < 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Approval Denied: Content contains {len(warnings)} active governance warning(s). Approving content with warnings requires a recorded justification comment (minimum 10 characters)."
                )
    else:
        # Rejection or Changes Requested requires explanation comments
        if not req.comments or not req.comments.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Decision comments are required when rejecting or requesting changes."
            )

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
        comments=req.comments.strip()
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
            "governance_run_id": latest_run.id if latest_run else None,
            "decision": req.decision,
            "decision_label": decision_label,
            "comments": req.comments.strip(),
            "warning_override": bool(warnings and req.decision == "approved")
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
