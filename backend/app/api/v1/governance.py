from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding
from app.models.knowledge import BrandAsset
from app.schemas.governance import (
    GovernanceRunRequest, GovernanceRunOut, GovernanceFindingOut,
    ImageGovernanceCheckRequest, ImageGovernanceCheckResult
)
from app.services.governance_engine import governance_engine
from app.services.image_governance import image_governance
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
    Produces explainable findings referencing approved knowledge or missing evidence.
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
        executed_by_user_id=current_user.id
    )

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

    findings = db.query(GovernanceFinding).filter(GovernanceFinding.governance_run_id == latest_run.id).all()
    out = GovernanceRunOut.model_validate(latest_run)
    out.findings = [GovernanceFindingOut.model_validate(f) for f in findings]
    return out


@router.post("/image-check", response_model=ImageGovernanceCheckResult)
def check_image_governance(
    req: ImageGovernanceCheckRequest,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Round 3 Improvement 3: Static-image governance inspection.
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
