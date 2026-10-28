from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, CorrectionSuggestion
from app.models.knowledge import BrandAsset
from app.schemas.governance import (
    GovernanceRunRequest, GovernanceRunOut, GovernanceFindingOut,
    ImageGovernanceCheckRequest, ImageGovernanceCheckResult,
    CorrectionSuggestionOut, CorrectionSuggestionApplyResponse, CorrectionSuggestionCustomApplyRequest
)
from app.services.governance_engine import governance_engine
from app.services.image_governance import image_governance
from app.services.suggestion_service import suggestion_service
from app.services.audit import log_audit_event
from app.api.deps import get_current_user, require_any_member, require_content_creator

router = APIRouter()

@router.post("/run", response_model=GovernanceRunOut)
def run_governance_check(
    req: GovernanceRunRequest,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 5 & 6: Execute deterministic governance rules against the specified content version.
    Produces explainable findings referencing approved knowledge or missing evidence,
    and generates context-preserving correction suggestions (Milestone 5D).
    """
    version = db.query(ContentVersion).filter(ContentVersion.id == req.content_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Content version not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == version.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Content does not belong to your organization.")

    # Execute deterministic governance engine
    run = governance_engine.evaluate_content_version(
        db=db,
        content_version=version,
        executed_by_user_id=current_user.id,
        product_id=req.product_id
    )

    # Milestone 5D: Generate explainable, context-preserving correction suggestions
    suggestion_service.generate_suggestions_for_run(db=db, run=run)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="GOVERNANCE_CHECK_RUN",
        entity_type="governance_run",
        entity_id=run.id,
        summary=f"Ran governance checks on '{item.title}' v{version.version_num}: {run.overall_status.upper()} ({run.findings_count} findings)",
        details={
            "content_version_id": version.id,
            "overall_status": run.overall_status,
            "findings_count": run.findings_count
        }
    )

    findings = db.query(GovernanceFinding).filter(GovernanceFinding.governance_run_id == run.id).all()
    out = GovernanceRunOut.model_validate(run)
    out.findings = [GovernanceFindingOut.model_validate(f) for f in findings]
    return out


@router.get("/runs/{version_id}/latest", response_model=GovernanceRunOut)
def get_latest_governance_run(
    version_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    version = db.query(ContentVersion).filter(ContentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Content version not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == version.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    latest_run = db.query(GovernanceRun).filter(
        GovernanceRun.content_version_id == version_id
    ).order_by(GovernanceRun.created_at.desc()).first()

    if not latest_run:
        raise HTTPException(status_code=404, detail="No governance runs recorded for this version.")

    # Ensure suggestions exist for latest run findings
    suggestion_service.generate_suggestions_for_run(db=db, run=latest_run)

    findings = db.query(GovernanceFinding).filter(GovernanceFinding.governance_run_id == latest_run.id).all()
    out = GovernanceRunOut.model_validate(latest_run)
    out.findings = [GovernanceFindingOut.model_validate(f) for f in findings]
    return out


@router.get("/runs/{version_id}/suggestions", response_model=List[CorrectionSuggestionOut])
def list_suggestions_for_version(
    version_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Retrieve all correction suggestions generated for the latest governance run on this version.
    """
    version = db.query(ContentVersion).filter(ContentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Content version not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == version.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    latest_run = db.query(GovernanceRun).filter(
        GovernanceRun.content_version_id == version_id
    ).order_by(GovernanceRun.created_at.desc()).first()

    if not latest_run:
        return []

    suggestions = suggestion_service.generate_suggestions_for_run(db=db, run=latest_run)
    return [CorrectionSuggestionOut.model_validate(s) for s in suggestions]


@router.get("/suggestions/{suggestion_id}", response_model=CorrectionSuggestionOut)
def get_suggestion_by_id(
    suggestion_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Correction suggestion not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == suggestion.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    return CorrectionSuggestionOut.model_validate(suggestion)


@router.post("/suggestions/{suggestion_id}/accept", response_model=CorrectionSuggestionApplyResponse)
def accept_suggestion(
    suggestion_id: str,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accept a correction suggestion:
    - Verifies checksum staleness.
    - If auto-applicable body text, creates a new ContentVersion with the edit applied,
      invalidating previous governance runs and resetting item status to draft.
    - If non-editable artwork (PDF or raster), records creator acceptance intent without
      falsely modifying the binary file, requiring revised asset re-upload.
    """
    suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Correction suggestion not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == suggestion.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    try:
        sug, content_item, new_ver, applied, msg = suggestion_service.accept_suggestion(
            db=db,
            suggestion_id=suggestion_id,
            user=current_user
        )
    except ValueError as e:
        err_msg = str(e)
        if "stale" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="SUGGESTION_ACCEPTED",
        entity_type="correction_suggestion",
        entity_id=sug.id,
        summary=f"Accepted suggestion for {sug.rule_code or sug.fact_key or 'finding'} on '{item.title}'",
        details={
            "applied_to_text": applied,
            "new_version_num": new_ver.version_num if new_ver else None,
            "target_type": sug.target_type,
            "page_number": sug.page_number
        }
    )

    return CorrectionSuggestionApplyResponse(
        suggestion=CorrectionSuggestionOut.model_validate(sug),
        content_item_id=content_item.id,
        new_version_num=new_ver.version_num if new_ver else None,
        new_version_id=new_ver.id if new_ver else None,
        applied_to_text=applied,
        message=msg
    )


@router.post("/suggestions/{suggestion_id}/reject", response_model=CorrectionSuggestionOut)
def reject_suggestion(
    suggestion_id: str,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reject a correction suggestion:
    Preserves content and version unchanged; does not resolve or suppress the finding.
    """
    suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Correction suggestion not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == suggestion.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    try:
        sug = suggestion_service.reject_suggestion(db=db, suggestion_id=suggestion_id, user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="SUGGESTION_REJECTED",
        entity_type="correction_suggestion",
        entity_id=sug.id,
        summary=f"Rejected suggestion for {sug.rule_code or sug.fact_key or 'finding'} on '{item.title}'",
        details={
            "finding_id": sug.finding_id,
            "target_type": sug.target_type
        }
    )

    return CorrectionSuggestionOut.model_validate(sug)


@router.post("/suggestions/{suggestion_id}/apply-custom", response_model=CorrectionSuggestionApplyResponse)
def apply_custom_suggestion(
    suggestion_id: str,
    req: CorrectionSuggestionCustomApplyRequest,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Apply a user-edited custom replacement text to resolve the finding in a new version.
    """
    suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Correction suggestion not found.")

    item = db.query(ContentItem).filter(
        ContentItem.id == suggestion.content_item_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    try:
        sug, content_item, new_ver, msg = suggestion_service.apply_custom_suggestion(
            db=db,
            suggestion_id=suggestion_id,
            custom_text=req.custom_text,
            user=current_user
        )
    except ValueError as e:
        err_msg = str(e)
        if "stale" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="SUGGESTION_CUSTOM_APPLIED",
        entity_type="correction_suggestion",
        entity_id=sug.id,
        summary=f"Applied custom correction for {sug.rule_code or 'finding'} on '{item.title}' (v{new_ver.version_num})",
        details={
            "custom_text": req.custom_text,
            "new_version_num": new_ver.version_num
        }
    )

    return CorrectionSuggestionApplyResponse(
        suggestion=CorrectionSuggestionOut.model_validate(sug),
        content_item_id=content_item.id,
        new_version_num=new_ver.version_num,
        new_version_id=new_ver.id,
        applied_to_text=True,
        message=msg
    )


@router.post("/image-check", response_model=ImageGovernanceCheckResult)
def check_image_governance(
    req: ImageGovernanceCheckRequest,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Static-image governance inspection.
    """
    file_path = None
    is_logo = False

    if req.asset_id:
        asset = db.query(BrandAsset).filter(
            BrandAsset.id == req.asset_id,
            BrandAsset.organization_id == membership.organization_id
        ).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Brand asset not found.")
        file_path = asset.file_path
        is_logo = (asset.asset_type == "logo")
    elif req.image_url:
        file_path = req.image_url
    else:
        raise HTTPException(status_code=400, detail="Must provide asset_id or image_url.")

    result = image_governance.inspect_image(
        file_path=file_path,
        channel=req.channel,
        alt_text=req.alt_text,
        is_logo=is_logo
    )

    return ImageGovernanceCheckResult(
        passed=result.get("passed", False),
        dimensions=result.get("dimensions"),
        aspect_ratio=result.get("aspect_ratio"),
        color_mode=result.get("color_mode"),
        findings=result.get("findings", []),
        recommendations=result.get("recommendations", [])
    )
