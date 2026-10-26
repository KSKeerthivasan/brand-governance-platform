from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.content import ContentItem, ContentVersion
from app.schemas.content import ContentItemCreate, ContentItemUpdate, ContentItemOut, ContentVersionOut
from app.api.deps import get_current_user, require_any_member, require_content_creator
from app.services.audit import log_audit_event

router = APIRouter()

@router.post("", response_model=ContentItemOut)
def create_content_item(
    req: ContentItemCreate,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 4: Create a new marketing content draft with initial ContentVersion (v1).
    """
    org_id = membership.organization_id

    content_item = ContentItem(
        organization_id=org_id,
        brand_id=req.brand_id,
        created_by=current_user.id,
        title=req.title,
        channel=req.channel,
        current_version_num=1,
        status="draft"
    )
    db.add(content_item)
    db.flush()

    checksum = ContentVersion.calculate_checksum(req.body_text)
    version = ContentVersion(
        content_item_id=content_item.id,
        version_num=1,
        body_text=req.body_text,
        checksum=checksum,
        created_by=current_user.id
    )
    db.add(version)
    db.commit()
    db.refresh(content_item)
    db.refresh(version)

    log_audit_event(
        db=db,
        organization_id=org_id,
        user_id=current_user.id,
        event_type="CONTENT_CREATED",
        entity_type="content_item",
        entity_id=content_item.id,
        summary=f"Created content draft '{content_item.title}' (v1)",
        details={"channel": req.channel, "checksum": checksum}
    )

    out = ContentItemOut.model_validate(content_item)
    out.latest_version = ContentVersionOut.model_validate(version)
    return out


@router.get("", response_model=List[ContentItemOut])
def list_content_items(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    items = db.query(ContentItem).filter(
        ContentItem.organization_id == membership.organization_id
    ).order_by(ContentItem.updated_at.desc()).all()

    result = []
    for item in items:
        latest_ver = db.query(ContentVersion).filter(
            ContentVersion.content_item_id == item.id,
            ContentVersion.version_num == item.current_version_num
        ).first()

        out = ContentItemOut.model_validate(item)
        if latest_ver:
            out.latest_version = ContentVersionOut.model_validate(latest_ver)
        result.append(out)

    return result


@router.get("/{content_id}", response_model=ContentItemOut)
def get_content_item(
    content_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    item = db.query(ContentItem).filter(
        ContentItem.id == content_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Content draft not found.")

    latest_ver = db.query(ContentVersion).filter(
        ContentVersion.content_item_id == item.id,
        ContentVersion.version_num == item.current_version_num
    ).first()

    out = ContentItemOut.model_validate(item)
    if latest_ver:
        out.latest_version = ContentVersionOut.model_validate(latest_ver)
    return out


@router.put("/{content_id}", response_model=ContentItemOut)
def update_content_item(
    content_id: str,
    req: ContentItemUpdate,
    membership: OrganizationMembership = Depends(require_content_creator),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 7: Version-aware revision.
    If the text changes or item was submitted/approved, a NEW version is created.
    Never mutates an already-submitted version or transfers approval to the new revision!
    """
    item = db.query(ContentItem).filter(
        ContentItem.id == content_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Content draft not found.")

    latest_ver = db.query(ContentVersion).filter(
        ContentVersion.content_item_id == item.id,
        ContentVersion.version_num == item.current_version_num
    ).first()

    text_changed = latest_ver and (latest_ver.body_text != req.body_text)

    if req.title:
        item.title = req.title
    if req.channel:
        item.channel = req.channel

    if text_changed or item.status in ["submitted", "approved", "changes_requested"]:
        # Create a new version
        new_version_num = item.current_version_num + 1
        new_checksum = ContentVersion.calculate_checksum(req.body_text)

        new_version = ContentVersion(
            content_item_id=item.id,
            version_num=new_version_num,
            body_text=req.body_text,
            checksum=new_checksum,
            created_by=current_user.id
        )
        db.add(new_version)
        item.current_version_num = new_version_num
        
        # Reset approval status back to draft
        old_status = item.status
        item.status = "draft"
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        db.refresh(new_version)

        log_audit_event(
            db=db,
            organization_id=membership.organization_id,
            user_id=current_user.id,
            event_type="CONTENT_REVISED",
            entity_type="content_version",
            entity_id=new_version.id,
            summary=f"Revised '{item.title}', generated v{new_version_num} (status reset from {old_status} to draft)",
            details={"previous_version": latest_ver.version_num if latest_ver else 1, "new_version": new_version_num}
        )

        out = ContentItemOut.model_validate(item)
        out.latest_version = ContentVersionOut.model_validate(new_version)
        return out
    else:
        # Only metadata changed, text is identical
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        out = ContentItemOut.model_validate(item)
        if latest_ver:
            out.latest_version = ContentVersionOut.model_validate(latest_ver)
        return out


@router.get("/{content_id}/versions", response_model=List[ContentVersionOut])
def list_content_versions(
    content_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    item = db.query(ContentItem).filter(
        ContentItem.id == content_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Content draft not found.")

    versions = db.query(ContentVersion).filter(
        ContentVersion.content_item_id == content_id
    ).order_by(ContentVersion.version_num.desc()).all()

    return versions
