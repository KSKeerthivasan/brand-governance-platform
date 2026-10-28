import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.content import ContentItem, ContentVersion
from app.schemas.content import ContentItemCreate, ContentItemUpdate, ContentItemOut, ContentVersionOut
from fastapi.security import HTTPAuthorizationCredentials
from app.api.deps import get_current_user, require_any_member, require_content_creator, security
from app.services.auth import decode_access_token
from app.services.audit import log_audit_event
from app.services.storage import storage_service

router = APIRouter()

def _build_version_out(ver: ContentVersion) -> ContentVersionOut:
    out = ContentVersionOut.model_validate(ver)
    if ver.poster_file_path:
        out.poster_url = f"/api/v1/content/versions/{ver.id}/poster"
        if ver.poster_file_path.lower().endswith(".pdf"):
            out.is_pdf = True
            try:
                from app.services.pdf_service import pdf_service
                if storage_service.check_exists(ver.poster_file_path):
                    local_p = storage_service.get_file_path_for_processing(ver.poster_file_path)
                    meta = pdf_service.validate_pdf_file(local_p)
                    out.page_count = meta.page_count
            except Exception:
                out.page_count = 1
    return out

@router.post("/upload-poster")
async def upload_poster(
    file: UploadFile = File(...),
    membership: OrganizationMembership = Depends(require_content_creator),
    db: Session = Depends(get_db)
):
    """
    Upload a poster image or multi-page marketing PDF to accompany a marketing content draft.
    """
    dest_path, bytes_written = await storage_service.save_file(
        file=file,
        org_id=membership.organization_id,
        subfolder="posters"
    )
    safe_filename = os.path.basename(dest_path)
    is_pdf = safe_filename.lower().endswith(".pdf") or (file.content_type == "application/pdf")
    local_path = storage_service.get_file_path_for_processing(dest_path)

    if is_pdf:
        from app.services.pdf_service import pdf_service, PDFValidationError
        try:
            pdf_meta = pdf_service.validate_pdf_file(local_path)
        except PDFValidationError as e:
            storage_service.delete_file(dest_path)
            raise HTTPException(status_code=400, detail=f"PDF validation failed: {str(e)}")

        first_p = pdf_meta.pages[0] if pdf_meta.pages else None
        return {
            "file_path": dest_path,
            "filename": safe_filename,
            "is_pdf": True,
            "width": first_p.width_px if first_p else 800,
            "height": first_p.height_px if first_p else 1000,
            "color_mode": "RGB",
            "format": "PDF",
            "size_bytes": bytes_written,
            "page_count": pdf_meta.page_count,
            "pages": [
                {
                    "page_number": p.page_number,
                    "width_pt": p.width_pt,
                    "height_pt": p.height_pt,
                    "width_px": p.width_px,
                    "height_px": p.height_px,
                    "orientation": p.orientation,
                    "aspect_ratio": p.aspect_ratio
                }
                for p in pdf_meta.pages
            ]
        }

    width, height, mode, format_name = None, None, "RGB", "PNG"
    try:
        from PIL import Image
        with Image.open(local_path) as img:
            width, height = img.size
            mode = img.mode
            format_name = img.format or "PNG"
    except Exception:
        pass

    return {
        "file_path": dest_path,
        "filename": safe_filename,
        "is_pdf": False,
        "width": width,
        "height": height,
        "color_mode": mode,
        "format": format_name,
        "size_bytes": bytes_written,
        "page_count": 1,
        "pages": []
    }

@router.get("/versions/{version_id}/poster")
def get_version_poster(
    version_id: str,
    page: Optional[int] = None,
    render: bool = False,
    token: Optional[str] = None,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Streams the attached poster image file or a rendered PDF page for a content version.
    Supports either Authorization header or ?token= query parameter for browser <img> tags.
    """
    actual_token = auth_credentials.credentials if auth_credentials else token
    if not actual_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    payload = decode_access_token(actual_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    version = db.query(ContentVersion).filter(ContentVersion.id == version_id).first()
    if not version or not version.poster_file_path:
        raise HTTPException(status_code=404, detail="Poster image not found.")

    item = db.query(ContentItem).filter(ContentItem.id == version.content_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content draft not found.")

    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == payload["sub"],
        OrganizationMembership.organization_id == item.organization_id
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    if not storage_service.check_exists(version.poster_file_path):
        raise HTTPException(status_code=404, detail="Poster file not found on disk or storage.")

    local_path = storage_service.get_file_path_for_processing(version.poster_file_path)

    if version.poster_file_path.lower().endswith(".pdf") or local_path.lower().endswith(".pdf"):
        from app.services.pdf_service import pdf_service
        if page is not None or render:
            page_to_render = page if (page is not None and page > 0) else 1
            cache_dir = os.path.join(os.path.dirname(local_path), f"pages_{version.id}")
            try:
                cached_png = pdf_service.get_or_render_page_cache(
                    file_path=local_path,
                    page_number=page_to_render,
                    cache_base_dir=cache_dir
                )
                return FileResponse(path=cached_png, media_type="image/png")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Could not render PDF page {page_to_render}: {str(e)}")
        return FileResponse(
            path=local_path,
            media_type="application/pdf",
            filename=os.path.basename(local_path)
        )

    import mimetypes
    media_type, _ = mimetypes.guess_type(local_path)
    return FileResponse(
        path=local_path,
        media_type=media_type or "image/png",
        filename=os.path.basename(local_path)
    )

@router.get("/versions/{version_id}/pdf-pages")
def get_version_pdf_pages(
    version_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Returns structured page metadata for a multi-page PDF attached to a content version.
    """
    version = db.query(ContentVersion).filter(ContentVersion.id == version_id).first()
    if not version or not version.poster_file_path:
        raise HTTPException(status_code=404, detail="Content version or creative asset not found.")

    item = db.query(ContentItem).filter(ContentItem.id == version.content_item_id).first()
    if not item or item.organization_id != membership.organization_id:
        raise HTTPException(status_code=403, detail="Tenant Isolation: Access denied.")

    if not version.poster_file_path.lower().endswith(".pdf"):
        return {"is_pdf": False, "page_count": 1, "pages": []}

    from app.services.pdf_service import pdf_service
    try:
        local_path = storage_service.get_file_path_for_processing(version.poster_file_path)
        meta = pdf_service.validate_pdf_file(local_path)
        return {
            "is_pdf": True,
            "page_count": meta.page_count,
            "pages": [
                {
                    "page_number": p.page_number,
                    "width_pt": p.width_pt,
                    "height_pt": p.height_pt,
                    "width_px": p.width_px,
                    "height_px": p.height_px,
                    "orientation": p.orientation,
                    "aspect_ratio": p.aspect_ratio,
                    "image_url": f"/api/v1/content/versions/{version.id}/poster?page={p.page_number}"
                }
                for p in meta.pages
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to inspect PDF pages: {str(e)}")

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

    checksum = ContentVersion.calculate_checksum(req.body_text, req.poster_file_path)
    version = ContentVersion(
        content_item_id=content_item.id,
        version_num=1,
        body_text=req.body_text,
        checksum=checksum,
        created_by=current_user.id,
        poster_file_path=req.poster_file_path,
        poster_asset_id=req.poster_asset_id,
        poster_alt_text=req.poster_alt_text
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
        details={
            "channel": req.channel,
            "checksum": checksum,
            "has_poster": bool(req.poster_file_path)
        }
    )

    out = ContentItemOut.model_validate(content_item)
    out.latest_version = _build_version_out(version)
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
            out.latest_version = _build_version_out(latest_ver)
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
        out.latest_version = _build_version_out(latest_ver)
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
    If the text or poster changes or item was submitted/approved, a NEW version is created.
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
    poster_changed = latest_ver and (
        (latest_ver.poster_file_path != req.poster_file_path) or
        (latest_ver.poster_alt_text != req.poster_alt_text)
    )
    title_changed = bool(req.title and item.title != req.title)
    channel_changed = bool(req.channel and item.channel != req.channel)

    if req.title:
        item.title = req.title
    if req.channel:
        item.channel = req.channel

    if text_changed or poster_changed or title_changed or channel_changed or item.status in ["submitted", "approved", "changes_requested"]:
        # Create a new version
        new_version_num = item.current_version_num + 1
        new_checksum = ContentVersion.calculate_checksum(req.body_text, req.poster_file_path)

        new_version = ContentVersion(
            content_item_id=item.id,
            version_num=new_version_num,
            body_text=req.body_text,
            checksum=new_checksum,
            created_by=current_user.id,
            poster_file_path=req.poster_file_path,
            poster_asset_id=req.poster_asset_id,
            poster_alt_text=req.poster_alt_text
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
            details={
                "previous_version": latest_ver.version_num if latest_ver else 1,
                "new_version": new_version_num,
                "has_poster": bool(req.poster_file_path),
                "checksum": new_checksum
            }
        )

        out = ContentItemOut.model_validate(item)
        out.latest_version = _build_version_out(new_version)
        return out
    else:
        # Only metadata changed, text and poster are identical
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        out = ContentItemOut.model_validate(item)
        if latest_ver:
            out.latest_version = _build_version_out(latest_ver)
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

    return [_build_version_out(v) for v in versions]
