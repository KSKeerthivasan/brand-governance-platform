import os
import json
import time
import logging
import uuid
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.knowledge import (
    KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset,
    KnowledgeBaseVersion, OrganizationActiveKnowledgeBase,
    StagedImport, StagedImportProductRow, StagedImportClaimRow, StagedImportDisclosureRow
)
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.brand import Brand, BrandProfile, BrandColor
from app.schemas.knowledge import (
    KnowledgeSourceOut,
    KnowledgeRuleOut, KnowledgeRuleCreate, KnowledgeRuleReview, KnowledgeRuleUpdate,
    KnowledgeFactOut, KnowledgeFactCreate, KnowledgeFactReview, KnowledgeFactUpdate,
    BrandAssetOut, BrandAssetReview,
    BrandColorIn, BrandColorOut, BrandProfileIn, BrandProfileOut,
    StagedImportPreviewOut, StagedRowPreview, KnowledgeBaseActivationIn, KnowledgeBaseActivationOut,
    LiveCheckRequest, LiveInfraction, LiveCheckResponse
)
from app.services.excel_service import excel_service
from app.services.rescore_service import rescore_service
from app.services.storage import storage_service
from app.services.knowledge_resolver import resolve_knowledge_base
from app.services.extraction import extract_pdf_text_and_candidates, extract_image_metadata
from app.services.evidence_validator import extract_pdf_pages
from app.services.gemini_extractor import GeminiConfigurationError, GeminiExtractionError
from app.services.audit import log_audit_event
from app.services.auth import decode_access_token
from app.api.deps import get_current_user, require_any_member, require_knowledge_reviewer, require_content_creator, security

CATEGORY_TITLE_MAP = {
    "pdf_brand_guidelines": "PDF Brand Guidelines (Retired)",
    "pdf_product_knowledge": "PDF Product Knowledge & Specs (Retired)",
    "supporting_doc": "Supporting Evidence Document",
    "brand_asset_image": "Brand Asset / Creative Image",
}

RETIRED_SOURCE_TYPES = {"pdf_brand_guidelines", "pdf_product_knowledge"}

router = APIRouter()


@router.post("/upload", response_model=KnowledgeSourceOut)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: str = Form(...),  # pdf_brand_guidelines, pdf_product_knowledge, supporting_doc, brand_asset_image
    brand_id: Optional[str] = Form(None),
    asset_type: Optional[str] = Form(None),
    usage_notes: Optional[str] = Form(None),
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload supporting evidence documents or brand creative assets.
    Note: 'pdf_brand_guidelines' and 'pdf_product_knowledge' onboarding categories are retired.
    Brand identity, products, claims, and disclosures are managed via structured forms and Excel imports.
    """
    if source_type in RETIRED_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The '{source_type}' onboarding category has been retired. "
                "Please use the Brand Profile Form, Product Catalogue Excel, "
                "Claims Register Excel, and Required Disclosures Excel for structured brand onboarding."
            )
        )

    org_id = membership.organization_id

    # Save file securely
    file_path, file_size = await storage_service.save_file(file, org_id, subfolder="knowledge")
    safe_filename = os.path.basename(file.filename or "uploaded_doc")

    # Derive title automatically from category if not provided
    effective_title = (title.strip() if title and title.strip() else None) or CATEGORY_TITLE_MAP.get(
        source_type, source_type.replace("_", " ").title()
    )

    # Deduplicate: Check if a KnowledgeSource already exists for this org, brand, and filename
    existing_source = db.query(KnowledgeSource).filter(
        KnowledgeSource.organization_id == org_id,
        KnowledgeSource.brand_id == brand_id,
        KnowledgeSource.filename == safe_filename
    ).first()

    if existing_source:
        source = existing_source
        source.file_path = file_path
        source.file_size_bytes = file_size
        source.mime_type = file.content_type or "application/octet-stream"
        source.version += 1
        source.status = "pending_review"
        # Purge only uncorrected pending candidate rules and facts for this source to avoid duplicates on retry
        db.query(KnowledgeRule).filter(
            KnowledgeRule.source_id == source.id,
            KnowledgeRule.status == "pending_review",
            KnowledgeRule.is_corrected == False
        ).delete(synchronize_session=False)
        db.query(KnowledgeFact).filter(
            KnowledgeFact.source_id == source.id,
            KnowledgeFact.status == "pending_review",
            KnowledgeFact.is_corrected == False
        ).delete(synchronize_session=False)
    else:
        # Create KnowledgeSource record in pending_review
        source = KnowledgeSource(
            organization_id=org_id,
            brand_id=brand_id,
            title=effective_title,
            source_type=source_type,
            filename=safe_filename,
            file_path=file_path,
            file_size_bytes=file_size,
            mime_type=file.content_type or "application/octet-stream",
            version=1,
            status="pending_review",  # Critical: never auto-approved!
            uploaded_by=current_user.id
        )
        db.add(source)
    db.flush()

    rules_created = 0
    facts_created = 0
    assets_created = 0
    t_upload_endpoint_start = time.perf_counter()
    extraction_timings: Dict[str, Any] = {}

    # Extract based on file type
    local_path = storage_service.get_file_path_for_processing(file_path)
    if file.content_type == "application/pdf" or safe_filename.lower().endswith(".pdf"):
        # Supporting evidence document: preserve file in storage without extracting candidate rules or facts.
        # Governance rules and facts are authored via structured Excel registers and Brand Profile.
        source.extracted_summary = f"Supporting evidence document: {safe_filename} ({file_size} bytes)."

    elif (file.content_type and file.content_type.startswith("image/")) or source_type == "brand_asset_image" or safe_filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
        meta = extract_image_metadata(local_path, safe_filename)
        effective_asset_type = asset_type.strip() if (asset_type and asset_type.strip()) else meta.get("asset_type", "campaign_creative")
        effective_asset_name = title.strip() if (title and title.strip()) else safe_filename
        asset_obj = BrandAsset(
            organization_id=org_id,
            brand_id=brand_id,
            source_id=source.id,
            asset_name=effective_asset_name,
            asset_type=effective_asset_type,
            file_path=file_path,
            mime_type=meta.get("mime_type", file.content_type or "image/png"),
            width=meta.get("width"),
            height=meta.get("height"),
            aspect_ratio=meta.get("aspect_ratio"),
            color_mode=meta.get("color_mode"),
            min_clearance_px=meta.get("min_clearance_px", 20),
            alt_text_required=True,
            usage_notes=usage_notes.strip() if (usage_notes and usage_notes.strip()) else None,
            status="pending_review"  # Starts in pending_review
        )
        db.add(asset_obj)
        assets_created += 1

    t_pers_start = time.perf_counter()
    try:
        db.commit()
        db.refresh(source)
    except Exception as pers_err:
        db.rollback()
        logger.error(f"Persistence transaction failed during upload: {pers_err}")
        raise HTTPException(
            status_code=500,
            detail=f"Database persistence failed during upload: {pers_err}"
        )
    persistence_ms = round((time.perf_counter() - t_pers_start) * 1000, 2)

    if extraction_timings:
        extraction_timings["persistence_ms"] = persistence_ms
        extraction_timings["total_elapsed_ms"] = round((time.perf_counter() - t_upload_endpoint_start) * 1000, 2)
        logger.info(f"EXTRACTION_STAGE_METRICS: {json.dumps(extraction_timings)}")

    # Log structured audit event
    log_audit_event(
        db=db,
        organization_id=org_id,
        user_id=current_user.id,
        event_type="KNOWLEDGE_UPLOADED",
        entity_type="knowledge_source",
        entity_id=source.id,
        summary=f"Uploaded {source_type} '{effective_title}' ({safe_filename}). Created candidate records.",
        details={
            "rules_candidate_count": rules_created,
            "facts_candidate_count": facts_created,
            "assets_candidate_count": assets_created,
            "status": "pending_review"
        }
    )

    out = KnowledgeSourceOut.model_validate(source)
    out.rules_count = rules_created
    out.facts_count = facts_created
    out.assets_count = assets_created
    return out


@router.get("/sources", response_model=List[KnowledgeSourceOut])
def list_knowledge_sources(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    sources = db.query(KnowledgeSource).filter(
        KnowledgeSource.organization_id == membership.organization_id
    ).order_by(KnowledgeSource.created_at.desc()).all()

    result = []
    for s in sources:
        r_cnt = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == s.id).count()
        f_cnt = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == s.id).count()
        a_cnt = db.query(BrandAsset).filter(BrandAsset.source_id == s.id).count()

        out = KnowledgeSourceOut.model_validate(s)
        out.rules_count = r_cnt
        out.facts_count = f_cnt
        out.assets_count = a_cnt
        result.append(out)

    return result


@router.get("/sources/{source_id}/text")
def get_knowledge_source_text(
    source_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Returns the extracted text per page from an uploaded knowledge source PDF.
    Enforces strict tenant isolation: users can only view documents from their own organization.
    """
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.organization_id == membership.organization_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")

    if not storage_service.check_exists(source.file_path):
        raise HTTPException(status_code=400, detail="Source file does not exist in storage.")

    local_path = storage_service.get_file_path_for_processing(source.file_path)
    pages = extract_pdf_pages(local_path)
    full_text = "\n\n".join(pages)

    return {
        "source_id": source.id,
        "title": source.title,
        "filename": source.filename,
        "total_pages": len(pages),
        "total_characters": len(full_text),
        "extracted_summary": source.extracted_summary,
        "pages": [{"page_number": idx, "text": p} for idx, p in enumerate(pages, 1)],
        "full_text": full_text
    }


@router.post("/sources/{source_id}/reprocess", response_model=KnowledgeSourceOut)
def reprocess_knowledge_source(
    source_id: str,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 9: Safe, controlled reprocessing of an existing uploaded source document.
    - Preserves all approved, rejected, and manually edited knowledge records.
    - Replaces only unreviewed machine-extracted pending candidates from this source.
    - Runs Gemini extraction with strict local schema and evidence validation.
    """
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.organization_id == membership.organization_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")

    if not storage_service.check_exists(source.file_path):
        raise HTTPException(
            status_code=400,
            detail=f"Source file no longer exists at '{source.file_path}'. Cannot reprocess."
        )

    local_path = storage_service.get_file_path_for_processing(source.file_path)

    # 1. Inspect existing rules and facts in a read-only manner
    existing_rules = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source.id).all()
    existing_facts = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source.id).all()

    # Preserved: records that were approved, rejected, deprecated, or edited by a reviewer
    preserved_rules = [r for r in existing_rules if r.status != "pending_review" or r.is_corrected]
    preserved_facts = [f for f in existing_facts if f.status != "pending_review" or f.is_corrected]

    # Replaceable: only machine-generated candidates that are still pending_review and never edited
    replaceable_rule_ids = [r.id for r in existing_rules if r.status == "pending_review" and not r.is_corrected]
    replaceable_fact_ids = [f.id for f in existing_facts if f.status == "pending_review" and not f.is_corrected]

    preserved_rule_codes = {r.rule_code for r in preserved_rules if r.rule_code}
    preserved_fact_keys = {(f.product_name, f.fact_key) for f in preserved_facts}

    # CRITICAL TRANSACTION SAFETY:
    # Do NOT delete or flush anything here. Release any active read transaction so the
    # database connection is idle and unblocked while waiting for Gemini remote API generation.
    db.rollback()

    t_reprocess_start = time.perf_counter()
    extraction_timings: Dict[str, Any] = {}

    # 2. Re-run Gemini extraction with strict schema & evidence verification.
    # Extraction output is kept entirely in-memory until validation completes successfully.
    try:
        summary, candidate_rules, candidate_facts, extraction_timings = extract_pdf_text_and_candidates(
            local_path, source.filename
        )
    except GeminiConfigurationError as gce:
        db.rollback()
        logger.warning(f"EXTRACTION_STAGE_METRICS: {json.dumps({'event': 'extraction_timing', 'filename': source.filename, 'outcome': 'failed', 'error': 'GeminiConfigurationError'})}")
        raise HTTPException(status_code=400, detail=f"Gemini configuration error: {gce}")
    except GeminiExtractionError as gee:
        db.rollback()
        logger.warning(f"EXTRACTION_STAGE_METRICS: {json.dumps({'event': 'extraction_timing', 'filename': source.filename, 'outcome': 'failed', 'error': 'GeminiExtractionError'})}")
        raise HTTPException(status_code=502, detail=f"Gemini extraction error: {gee}")
    except Exception as ex:
        db.rollback()
        logger.warning(f"EXTRACTION_STAGE_METRICS: {json.dumps({'event': 'extraction_timing', 'filename': source.filename, 'outcome': 'failed', 'error': str(ex)})}")
        raise HTTPException(status_code=500, detail=f"Reprocessing error: {ex}")

    # 3. Open a short database transaction to atomically delete replaceable records and insert new candidates
    t_pers_start = time.perf_counter()
    new_rules_count = 0
    new_facts_count = 0

    try:
        # Re-fetch source within the write transaction
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == source_id,
            KnowledgeSource.organization_id == membership.organization_id
        ).first()
        if not source:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")

        # Atomically delete only replaceable pending uncorrected records
        if replaceable_rule_ids:
            db.query(KnowledgeRule).filter(KnowledgeRule.id.in_(replaceable_rule_ids)).delete(synchronize_session=False)
        if replaceable_fact_ids:
            db.query(KnowledgeFact).filter(KnowledgeFact.id.in_(replaceable_fact_ids)).delete(synchronize_session=False)

        # Update source metadata
        source.extracted_summary = summary
        source.version = (source.version or 1) + 1

        # Insert new validated candidate rules
        for r in candidate_rules:
            # Avoid creating duplicate candidate if the rule code is already preserved
            if r.get("rule_code") and r["rule_code"] in preserved_rule_codes:
                continue

            rule_obj = KnowledgeRule(
                organization_id=membership.organization_id,
                brand_id=source.brand_id,
                source_id=source.id,
                rule_type=r["rule_type"],
                title=r["title"],
                pattern=r["pattern"],
                explanation=r["explanation"],
                severity=r["severity"],
                context_condition=r.get("context_condition"),
                source_citation=r.get("source_citation"),
                rule_code=r.get("rule_code"),
                source_status=r.get("source_status", "unknown"),
                enforcement_action=r.get("enforcement_action", "flag_for_review"),
                rationale=r.get("rationale"),
                recommended_alternatives=r.get("recommended_alternatives"),
                exceptions=r.get("exceptions"),
                examples_bad=r.get("examples_bad"),
                examples_good=r.get("examples_good"),
                evidence_passage=r.get("evidence_passage"),
                page_number=r.get("page_number"),
                evidence_validation=r.get("evidence_validation", "unverified"),
                uncertainty_notes=r.get("uncertainty_notes"),
                original_extraction=r.get("original_extraction"),
                is_corrected=False,
                status="pending_review"
            )
            db.add(rule_obj)
            new_rules_count += 1

        # Insert new validated candidate facts
        for f in candidate_facts:
            if (f["product_name"], f["fact_key"]) in preserved_fact_keys:
                continue

            fact_obj = KnowledgeFact(
                organization_id=membership.organization_id,
                brand_id=source.brand_id,
                source_id=source.id,
                product_name=f["product_name"],
                category=f["category"],
                fact_key=f["fact_key"],
                fact_value=f["fact_value"],
                supporting_evidence=f.get("supporting_evidence"),
                source_citation=f.get("source_citation"),
                product_id=f.get("product_id"),
                unit=f.get("unit"),
                value_status=f.get("value_status", "explicitly_stated"),
                source_status=f.get("source_status", "approved"),
                page_number=f.get("page_number"),
                evidence_validation=f.get("evidence_validation", "unverified"),
                uncertainty_notes=f.get("uncertainty_notes"),
                original_extraction=f.get("original_extraction"),
                is_corrected=False,
                status="pending_review"
            )
            db.add(fact_obj)
            new_facts_count += 1

        # Atomically commit deletions and insertions
        db.commit()
        db.refresh(source)
    except Exception as pers_err:
        db.rollback()
        logger.error(f"Persistence transaction failed during reprocessing: {pers_err}")
        if isinstance(pers_err, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Database persistence failed during reprocessing: {pers_err}. Existing records preserved."
        )

    persistence_ms = round((time.perf_counter() - t_pers_start) * 1000, 2)
    if extraction_timings:
        extraction_timings["persistence_ms"] = persistence_ms
        extraction_timings["total_elapsed_ms"] = round((time.perf_counter() - t_reprocess_start) * 1000, 2)
        logger.info(f"EXTRACTION_STAGE_METRICS: {json.dumps(extraction_timings)}")
        try:
            metrics_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports", "extraction_benchmark_metrics.json"))
            os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
            with open(metrics_file, "w", encoding="utf-8") as bf:
                json.dump(extraction_timings, bf, indent=2)
        except Exception as dump_err:
            logger.warning(f"Failed to persist benchmark metrics file: {dump_err}")

    # 4. Record audit event ONLY after successful atomic commit
    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="KNOWLEDGE_REPROCESSED",
        entity_type="knowledge_source",
        entity_id=source.id,
        summary=f"Reprocessed '{source.title}'. Preserved {len(preserved_rules)} reviewed rules, created {new_rules_count} new candidate rules.",
        details={
            "preserved_rules_count": len(preserved_rules),
            "replaced_rules_count": len(replaceable_rule_ids),
            "new_candidate_rules_count": new_rules_count,
            "preserved_facts_count": len(preserved_facts),
            "replaced_facts_count": len(replaceable_fact_ids),
            "new_candidate_facts_count": new_facts_count,
            "new_version": source.version
        }
    )

    out = KnowledgeSourceOut.model_validate(source)
    out.rules_count = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source.id).count()
    out.facts_count = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source.id).count()
    out.assets_count = db.query(BrandAsset).filter(BrandAsset.source_id == source.id).count()
    return out


@router.get("/rules", response_model=List[KnowledgeRuleOut])
def list_knowledge_rules(
    status_filter: Optional[str] = None,
    rule_type: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    query = db.query(KnowledgeRule).filter(
        KnowledgeRule.organization_id == membership.organization_id
    )
    if status_filter:
        query = query.filter(KnowledgeRule.status == status_filter)
    if rule_type:
        query = query.filter(KnowledgeRule.rule_type == rule_type)

    return query.order_by(KnowledgeRule.created_at.desc()).all()


@router.post("/rules", response_model=KnowledgeRuleOut)
def create_knowledge_rule(
    req: KnowledgeRuleCreate,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rule = KnowledgeRule(
        organization_id=membership.organization_id,
        brand_id=req.brand_id,
        source_id=req.source_id,
        rule_type=req.rule_type,
        title=req.title,
        pattern=req.pattern,
        explanation=req.explanation,
        severity=req.severity,
        context_condition=req.context_condition,
        source_citation=req.source_citation,
        rule_code=req.rule_code,
        source_status=req.source_status or "unknown",
        enforcement_action=req.enforcement_action or "flag_for_review",
        rationale=req.rationale,
        recommended_alternatives=req.recommended_alternatives,
        exceptions=req.exceptions,
        examples_bad=req.examples_bad,
        examples_good=req.examples_good,
        evidence_passage=req.evidence_passage,
        page_number=req.page_number,
        evidence_validation=req.evidence_validation or "unverified",
        uncertainty_notes=req.uncertainty_notes,
        is_corrected=False,
        status="pending_review"  # New rules start pending review
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="RULE_CANDIDATE_CREATED",
        entity_type="knowledge_rule",
        entity_id=rule.id,
        summary=f"Added candidate rule '{rule.title}'",
        details={"pattern": rule.pattern, "severity": rule.severity}
    )
    return rule


@router.put("/rules/{rule_id}", response_model=KnowledgeRuleOut)
def update_knowledge_rule(
    rule_id: str,
    req: KnowledgeRuleUpdate,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 8: Allow authorized Knowledge Reviewer to correct extracted content before approving it.
    Preserves original machine extraction and records reviewer corrections.
    """
    rule = db.query(KnowledgeRule).filter(
        KnowledgeRule.id == rule_id,
        KnowledgeRule.organization_id == membership.organization_id
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Knowledge rule not found.")

    corrections = {}
    if req.title is not None and req.title != rule.title:
        corrections["title"] = {"old": rule.title, "new": req.title}
        rule.title = req.title
    if req.pattern is not None and req.pattern != rule.pattern:
        corrections["pattern"] = {"old": rule.pattern, "new": req.pattern}
        rule.pattern = req.pattern
    if req.explanation is not None and req.explanation != rule.explanation:
        corrections["explanation"] = {"old": rule.explanation, "new": req.explanation}
        rule.explanation = req.explanation
    if req.severity is not None and req.severity != rule.severity:
        corrections["severity"] = {"old": rule.severity, "new": req.severity}
        rule.severity = req.severity
    if req.rule_type is not None and req.rule_type != rule.rule_type:
        corrections["rule_type"] = {"old": rule.rule_type, "new": req.rule_type}
        rule.rule_type = req.rule_type
    if req.context_condition is not None and req.context_condition != rule.context_condition:
        corrections["context_condition"] = {"old": rule.context_condition, "new": req.context_condition}
        rule.context_condition = req.context_condition
    if req.recommended_alternatives is not None:
        rule.recommended_alternatives = req.recommended_alternatives
    if req.exceptions is not None:
        rule.exceptions = req.exceptions
    if req.review_notes is not None:
        rule.review_notes = req.review_notes

    if corrections:
        rule.is_corrected = True

    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="RULE_CORRECTED",
        entity_type="knowledge_rule",
        entity_id=rule.id,
        summary=f"Reviewer corrected candidate rule '{rule.title}'",
        details={"corrections": corrections, "notes": req.review_notes}
    )
    return rule


@router.post("/rules/{rule_id}/review", response_model=KnowledgeRuleOut)
def review_knowledge_rule(
    rule_id: str,
    req: KnowledgeRuleReview,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 3: Human Knowledge Reviewer approves, rejects, or deprecates candidate rule.
    """
    rule = db.query(KnowledgeRule).filter(
        KnowledgeRule.id == rule_id,
        KnowledgeRule.organization_id == membership.organization_id
    ).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Knowledge rule not found.")

    if req.status not in ["approved", "rejected", "deprecated"]:
        raise HTTPException(status_code=400, detail="Status must be approved, rejected, or deprecated.")

    old_status = rule.status
    rule.status = req.status
    rule.reviewed_by = current_user.id
    rule.reviewed_at = datetime.utcnow()
    rule.review_notes = req.review_notes

    if req.corrected_title:
        rule.title = req.corrected_title
        rule.is_corrected = True
    if req.corrected_pattern:
        rule.pattern = req.corrected_pattern
        rule.is_corrected = True
    if req.corrected_explanation:
        rule.explanation = req.corrected_explanation
        rule.is_corrected = True

    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type=f"RULE_{req.status.upper()}",
        entity_type="knowledge_rule",
        entity_id=rule.id,
        summary=f"Reviewer changed rule '{rule.title}' status from {old_status} to {req.status}",
        details={
            "notes": req.review_notes,
            "is_corrected": rule.is_corrected,
            "source_status": rule.source_status
        }
    )
    return rule


@router.get("/facts", response_model=List[KnowledgeFactOut])
def list_knowledge_facts(
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    query = db.query(KnowledgeFact).filter(
        KnowledgeFact.organization_id == membership.organization_id
    )
    if status_filter:
        query = query.filter(KnowledgeFact.status == status_filter)
    if category:
        query = query.filter(KnowledgeFact.category == category)

    return query.order_by(KnowledgeFact.created_at.desc()).all()


@router.post("/facts", response_model=KnowledgeFactOut)
def create_knowledge_fact(
    req: KnowledgeFactCreate,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fact = KnowledgeFact(
        organization_id=membership.organization_id,
        brand_id=req.brand_id,
        source_id=req.source_id,
        product_name=req.product_name,
        category=req.category,
        fact_key=req.fact_key,
        fact_value=req.fact_value,
        supporting_evidence=req.supporting_evidence,
        source_citation=req.source_citation,
        product_id=req.product_id,
        unit=req.unit,
        value_status=req.value_status or "explicitly_stated",
        source_status=req.source_status or "approved",
        page_number=req.page_number,
        evidence_validation=req.evidence_validation or "unverified",
        uncertainty_notes=req.uncertainty_notes,
        valid_from=req.valid_from,
        valid_until=req.valid_until,
        is_corrected=False,
        status="pending_review"  # New facts start pending review
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="FACT_CANDIDATE_CREATED",
        entity_type="knowledge_fact",
        entity_id=fact.id,
        summary=f"Added candidate fact '{fact.fact_key}' for {fact.product_name}",
        details={"value": fact.fact_value}
    )
    return fact


@router.put("/facts/{fact_id}", response_model=KnowledgeFactOut)
def update_knowledge_fact(
    fact_id: str,
    req: KnowledgeFactUpdate,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 8: Allow authorized Knowledge Reviewer to correct extracted product fact or claim before approval.
    """
    fact = db.query(KnowledgeFact).filter(
        KnowledgeFact.id == fact_id,
        KnowledgeFact.organization_id == membership.organization_id
    ).first()

    if not fact:
        raise HTTPException(status_code=404, detail="Knowledge fact not found.")

    corrections = {}
    if req.product_name is not None and req.product_name != fact.product_name:
        corrections["product_name"] = {"old": fact.product_name, "new": req.product_name}
        fact.product_name = req.product_name
    if req.category is not None and req.category != fact.category:
        corrections["category"] = {"old": fact.category, "new": req.category}
        fact.category = req.category
    if req.fact_key is not None and req.fact_key != fact.fact_key:
        corrections["fact_key"] = {"old": fact.fact_key, "new": req.fact_key}
        fact.fact_key = req.fact_key
    if req.fact_value is not None and req.fact_value != fact.fact_value:
        corrections["fact_value"] = {"old": fact.fact_value, "new": req.fact_value}
        fact.fact_value = req.fact_value
    if req.supporting_evidence is not None:
        fact.supporting_evidence = req.supporting_evidence
    if req.unit is not None:
        fact.unit = req.unit
    if req.review_notes is not None:
        fact.review_notes = req.review_notes

    if corrections:
        fact.is_corrected = True

    db.commit()
    db.refresh(fact)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="FACT_CORRECTED",
        entity_type="knowledge_fact",
        entity_id=fact.id,
        summary=f"Reviewer corrected candidate fact '{fact.fact_key}'",
        details={"corrections": corrections, "notes": req.review_notes}
    )
    return fact


@router.post("/facts/{fact_id}/review", response_model=KnowledgeFactOut)
def review_knowledge_fact(
    fact_id: str,
    req: KnowledgeFactReview,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 3: Human Knowledge Reviewer approves, rejects, or expires candidate fact.
    """
    fact = db.query(KnowledgeFact).filter(
        KnowledgeFact.id == fact_id,
        KnowledgeFact.organization_id == membership.organization_id
    ).first()

    if not fact:
        raise HTTPException(status_code=404, detail="Knowledge fact not found.")

    if req.status not in ["approved", "rejected", "expired"]:
        raise HTTPException(status_code=400, detail="Status must be approved, rejected, or expired.")

    old_status = fact.status
    fact.status = req.status
    fact.reviewed_by = current_user.id
    fact.reviewed_at = datetime.utcnow()
    fact.review_notes = req.review_notes

    if req.corrected_fact_key:
        fact.fact_key = req.corrected_fact_key
        fact.is_corrected = True
    if req.corrected_fact_value:
        fact.fact_value = req.corrected_fact_value
        fact.is_corrected = True

    db.commit()
    db.refresh(fact)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type=f"FACT_{req.status.upper()}",
        entity_type="knowledge_fact",
        entity_id=fact.id,
        summary=f"Reviewer changed fact '{fact.fact_key}' status from {old_status} to {req.status}",
        details={
            "notes": req.review_notes,
            "is_corrected": fact.is_corrected,
            "source_status": fact.source_status
        }
    )
    return fact


@router.get("/assets", response_model=List[BrandAssetOut])
def list_brand_assets(
    status_filter: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    query = db.query(BrandAsset).filter(
        BrandAsset.organization_id == membership.organization_id
    )
    if status_filter:
        query = query.filter(BrandAsset.status == status_filter)
    return query.order_by(BrandAsset.created_at.desc()).all()


@router.post("/assets/{asset_id}/review", response_model=BrandAssetOut)
def review_brand_asset(
    asset_id: str,
    req: BrandAssetReview,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(BrandAsset).filter(
        BrandAsset.id == asset_id,
        BrandAsset.organization_id == membership.organization_id
    ).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Brand asset not found.")

    asset.status = req.status
    asset.reviewed_by = current_user.id
    asset.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type=f"ASSET_{req.status.upper()}",
        entity_type="brand_asset",
        entity_id=asset.id,
        summary=f"Reviewer set asset '{asset.asset_name}' status to {req.status}",
        details={}
    )
    return asset


@router.get("/assets/{asset_id}/file")
def get_brand_asset_file(
    asset_id: str,
    token: Optional[str] = None,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Streams the brand asset file.
    Supports Authorization header or ?token= parameter for img tags.
    """
    actual_token = auth_credentials.credentials if auth_credentials else token
    if not actual_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    payload = decode_access_token(actual_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    asset = db.query(BrandAsset).filter(BrandAsset.id == asset_id).first()
    if not asset or not asset.file_path:
        raise HTTPException(status_code=404, detail="Asset not found or no file path.")

    if not storage_service.check_exists(asset.file_path):
        raise HTTPException(status_code=404, detail="Asset file not found.")

    local_asset_path = storage_service.get_file_path_for_processing(asset.file_path)
    media_type = asset.mime_type or "image/png"
    return FileResponse(local_asset_path, media_type=media_type)


# -----------------------------------------------------------------------------
# ROUND 3: STRUCTURED KNOWLEDGE & STAGED EXCEL INGESTION ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/templates/{template_type}")
def download_excel_template(
    template_type: str
):
    """
    Downloads authoritative Excel template (.xlsx) for bulk ingestion.
    Supported types: 'product_catalogue', 'claims_and_disclosures'.
    Contains standard blank schemas; accessible without auth blocking.
    """
    if template_type not in ("product_catalogue", "claims_and_disclosures"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported template type '{template_type}'. Permitted: 'product_catalogue', 'claims_and_disclosures'"
        )

    content = excel_service.generate_template(template_type)
    filename = f"{template_type}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.post("/import/{import_type}/preview", response_model=StagedImportPreviewOut)
async def preview_staged_excel_import(
    import_type: str,
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Form(None),
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Uploads and validates an Excel workbook, staging rows into staging tables.
    CRITICAL: Does NOT mutate active Product, Claim, or Disclosure records!
    Returns full row-by-row preview with validation errors.
    """
    if import_type not in ("product_catalogue", "claims_and_disclosures"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported import type '{import_type}'. Permitted: 'product_catalogue', 'claims_and_disclosures'"
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    effective_idempotency_key = idempotency_key or hashlib.sha256(file_bytes).hexdigest()[:32]
    org_id = membership.organization_id

    staged_import = excel_service.parse_and_stage_excel(
        db=db,
        org_id=org_id,
        user_id=current_user.id,
        file_name=file.filename or "import.xlsx",
        file_bytes=file_bytes,
        idempotency_key=effective_idempotency_key,
        import_type=import_type
    )

    # Collect row previews
    preview_rows: List[StagedRowPreview] = []
    if import_type == "product_catalogue":
        p_rows = db.query(StagedImportProductRow).filter(
            StagedImportProductRow.organization_id == org_id,
            StagedImportProductRow.import_id == staged_import.id
        ).order_by(StagedImportProductRow.row_number).all()
        for r in p_rows:
            preview_rows.append(StagedRowPreview(
                row_number=r.row_number,
                raw_data=r.raw_data or {},
                parsed_data=r.parsed_data,
                validation_errors=r.validation_errors or [],
                is_valid=r.is_valid,
                sheet_name="Product_Catalogue"
            ))
    elif import_type == "claims_and_disclosures":
        c_rows = db.query(StagedImportClaimRow).filter(
            StagedImportClaimRow.organization_id == org_id,
            StagedImportClaimRow.import_id == staged_import.id
        ).order_by(StagedImportClaimRow.row_number).all()
        for r in c_rows:
            preview_rows.append(StagedRowPreview(
                row_number=r.row_number,
                raw_data=r.raw_data or {},
                parsed_data=r.parsed_data,
                validation_errors=r.validation_errors or [],
                is_valid=r.is_valid,
                sheet_name="Claims_Register"
            ))
        d_rows = db.query(StagedImportDisclosureRow).filter(
            StagedImportDisclosureRow.organization_id == org_id,
            StagedImportDisclosureRow.import_id == staged_import.id
        ).order_by(StagedImportDisclosureRow.row_number).all()
        for r in d_rows:
            preview_rows.append(StagedRowPreview(
                row_number=r.row_number,
                raw_data=r.raw_data or {},
                parsed_data=r.parsed_data,
                validation_errors=r.validation_errors or [],
                is_valid=r.is_valid,
                sheet_name="Required_Disclosures"
            ))

    out = StagedImportPreviewOut.model_validate(staged_import)
    out.rows = preview_rows
    return out


@router.get("/import/{import_id}/preview", response_model=StagedImportPreviewOut)
def get_staged_import_preview(
    import_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Retrieves existing staged import preview and row validation details.
    """
    org_id = membership.organization_id
    staged_import = db.query(StagedImport).filter(
        StagedImport.organization_id == org_id,
        StagedImport.id == import_id
    ).first()

    if not staged_import:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staged import session not found.")

    preview_rows: List[StagedRowPreview] = []
    if staged_import.import_type == "product_catalogue":
        p_rows = db.query(StagedImportProductRow).filter(
            StagedImportProductRow.organization_id == org_id,
            StagedImportProductRow.import_id == staged_import.id
        ).order_by(StagedImportProductRow.row_number).all()
        for r in p_rows:
            preview_rows.append(StagedRowPreview(
                row_number=r.row_number,
                raw_data=r.raw_data or {},
                parsed_data=r.parsed_data,
                validation_errors=r.validation_errors or [],
                is_valid=r.is_valid,
                sheet_name="Product_Catalogue"
            ))
    elif staged_import.import_type == "claims_and_disclosures":
        c_rows = db.query(StagedImportClaimRow).filter(
            StagedImportClaimRow.organization_id == org_id,
            StagedImportClaimRow.import_id == staged_import.id
        ).order_by(StagedImportClaimRow.row_number).all()
        for r in c_rows:
            preview_rows.append(StagedRowPreview(
                row_number=r.row_number,
                raw_data=r.raw_data or {},
                parsed_data=r.parsed_data,
                validation_errors=r.validation_errors or [],
                is_valid=r.is_valid,
                sheet_name="Claims_Register"
            ))
        d_rows = db.query(StagedImportDisclosureRow).filter(
            StagedImportDisclosureRow.organization_id == org_id,
            StagedImportDisclosureRow.import_id == staged_import.id
        ).order_by(StagedImportDisclosureRow.row_number).all()
        for r in d_rows:
            preview_rows.append(StagedRowPreview(
                row_number=r.row_number,
                raw_data=r.raw_data or {},
                parsed_data=r.parsed_data,
                validation_errors=r.validation_errors or [],
                is_valid=r.is_valid,
                sheet_name="Required_Disclosures"
            ))

    out = StagedImportPreviewOut.model_validate(staged_import)
    out.rows = preview_rows
    return out


@router.post("/import/{import_id}/confirm")
def confirm_staged_import(
    import_id: str,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atomically commits a validated staged import into active product/claim tables.
    If validation errors exist or any row fails, the transaction is completely rolled back.
    """
    try:
        result = excel_service.confirm_staged_import(
            db=db,
            org_id=membership.organization_id,
            import_id=import_id,
            user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except RuntimeError as re_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(re_err))

    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=current_user.id,
        event_type="EXCEL_IMPORT_CONFIRMED",
        entity_type="staged_import",
        entity_id=import_id,
        summary=f"Confirmed staged Excel import {import_id} ({result.get('import_type')})",
        details=result
    )

    return result


@router.post("/import/{import_id}/discard")
def discard_staged_import(
    import_id: str,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    db: Session = Depends(get_db)
):
    """
    Discards a staged import session without modifying any active records.
    """
    excel_service.discard_staged_import(db, membership.organization_id, import_id)
    return {"status": "discarded", "import_id": import_id}


@router.get("/brand-profile", response_model=BrandProfileOut)
def get_brand_profile(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Retrieves the structured Brand Profile and associated Brand Colors for the organization.
    """
    org_id = membership.organization_id
    profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found for this organization. Please create one."
        )

    colors = db.query(BrandColor).filter(BrandColor.brand_profile_id == profile.id).all()
    out = BrandProfileOut.model_validate(profile)
    out.colors = [BrandColorOut.model_validate(c) for c in colors]
    return out


@router.post("/brand-profile", response_model=BrandProfileOut)
def save_brand_profile(
    req: BrandProfileIn,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Saves or updates the structured Brand Profile and atomic Brand Colors.
    Ensures minimum required fields (Section 2.7 of specification) are enforced.
    """
    org_id = membership.organization_id

    # Resolve Brand record
    brand = db.query(Brand).filter(Brand.organization_id == org_id).first()
    if not brand:
        brand = Brand(
            organization_id=org_id,
            name=req.brand_name.strip(),
            description=req.brand_description.strip()
        )
        db.add(brand)
        db.flush()

    profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org_id).first()
    if not profile:
        profile = BrandProfile(
            organization_id=org_id,
            brand_name=req.brand_name,
            brand_description=req.brand_description or "",
            approved_taglines=req.approved_taglines,
            brand_personality=req.brand_personality,
            preferred_tone=req.preferred_tone,
            tones_to_avoid=req.tones_to_avoid,
            preferred_terminology=req.preferred_terminology,
            prohibited_terminology=req.prohibited_terminology,
            writing_style=req.writing_style,
            spelling_convention=req.spelling_convention,
            writing_style_instructions=req.writing_style_instructions,
            approved_languages=req.approved_languages,
            primary_heading_font=req.primary_heading_font or "Inter",
            secondary_body_font=req.secondary_body_font or "Roboto",
            additional_approved_fonts=req.additional_approved_fonts,
            typography_instructions=req.typography_instructions,
            visual_style=req.visual_style,
            preferred_imagery_style=req.preferred_imagery_style,
            preferred_backgrounds=req.preferred_backgrounds,
            preferred_visual_treatments=req.preferred_visual_treatments,
            visual_styles_to_avoid=req.visual_styles_to_avoid,
            logo_usage_instructions=req.logo_usage_instructions
        )
        db.add(profile)
        db.flush()
    else:
        profile.brand_name = req.brand_name
        profile.brand_description = req.brand_description or ""
        profile.approved_taglines = req.approved_taglines
        profile.brand_personality = req.brand_personality
        profile.preferred_tone = req.preferred_tone
        profile.tones_to_avoid = req.tones_to_avoid
        profile.preferred_terminology = req.preferred_terminology
        profile.prohibited_terminology = req.prohibited_terminology
        profile.writing_style = req.writing_style
        profile.spelling_convention = req.spelling_convention
        profile.writing_style_instructions = req.writing_style_instructions
        profile.approved_languages = req.approved_languages
        profile.primary_heading_font = req.primary_heading_font or "Inter"
        profile.secondary_body_font = req.secondary_body_font or "Roboto"
        profile.additional_approved_fonts = req.additional_approved_fonts
        profile.typography_instructions = req.typography_instructions
        profile.visual_style = req.visual_style
        profile.preferred_imagery_style = req.preferred_imagery_style
        profile.preferred_backgrounds = req.preferred_backgrounds
        profile.preferred_visual_treatments = req.preferred_visual_treatments
        profile.visual_styles_to_avoid = req.visual_styles_to_avoid
        profile.logo_usage_instructions = req.logo_usage_instructions
        profile.updated_at = datetime.utcnow()

    # Atomically replace brand colors
    db.query(BrandColor).filter(BrandColor.brand_profile_id == profile.id).delete()
    new_colors = []
    for c in req.colors:
        color_obj = BrandColor(
            organization_id=org_id,
            brand_profile_id=profile.id,
            colour_name=c.colour_name,
            colour_family=c.colour_family,
            colour_role=c.colour_role,
            hex_value=c.hex_value,
            rgb_r=c.rgb_r,
            rgb_g=c.rgb_g,
            rgb_b=c.rgb_b,
            usage_instructions=c.usage_instructions
        )
        db.add(color_obj)
        new_colors.append(color_obj)

    db.commit()
    db.refresh(profile)

    log_audit_event(
        db=db,
        organization_id=org_id,
        user_id=current_user.id,
        event_type="BRAND_PROFILE_SAVED",
        entity_type="brand_profile",
        entity_id=profile.id,
        summary=f"Saved structured Brand Profile for '{profile.brand_name}' with {len(new_colors)} colors",
        details={"colors_count": len(new_colors), "fonts": [profile.primary_heading_font, profile.secondary_body_font]}
    )

    out = BrandProfileOut.model_validate(profile)
    out.colors = [BrandColorOut.model_validate(c) for c in new_colors]
    return out


@router.post("/activate", response_model=KnowledgeBaseActivationOut)
def activate_knowledge_base(
    payload: Optional[KnowledgeBaseActivationIn] = None,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assembles complete immutable Knowledge Base Manifest (Brand Profile, Colors, Products,
    Claims, Disclosures, Assets) and activates it with SHA-256 integrity hash.
    Protected at the database level against mutation or deletion.
    """
    org_id = membership.organization_id

    # Validate BrandProfile exists
    brand_profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org_id).first()
    if not brand_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate knowledge base: Brand Profile must be created and saved first."
        )

    colors = db.query(BrandColor).filter(BrandColor.organization_id == org_id).all()
    products = db.query(Product).filter(Product.organization_id == org_id).all()
    claims = db.query(Claim).filter(Claim.organization_id == org_id).all()
    disclosures = db.query(RequiredDisclosure).filter(RequiredDisclosure.organization_id == org_id).all()
    assets = db.query(BrandAsset).filter(
        BrandAsset.organization_id == org_id,
        BrandAsset.status == "approved"
    ).all()
    rules = db.query(KnowledgeRule).filter(
        KnowledgeRule.organization_id == org_id,
        KnowledgeRule.status == "approved"
    ).all()
    facts = db.query(KnowledgeFact).filter(
        KnowledgeFact.organization_id == org_id,
        KnowledgeFact.status == "approved"
    ).all()

    # Determine next version number
    latest_ver = db.query(KnowledgeBaseVersion).filter(
        KnowledgeBaseVersion.organization_id == org_id
    ).order_by(KnowledgeBaseVersion.version_num.desc()).first()

    next_version = (latest_ver.version_num + 1) if latest_ver else 1

    colors_snapshot = [
        {"name": c.colour_name, "family": c.colour_family, "role": c.colour_role, "hex": c.hex_value, "rgb": [c.rgb_r, c.rgb_g, c.rgb_b]}
        for c in colors
    ]
    products_snapshot = [
        {
            "product_id": p.product_id,
            "name": p.product_name,
            "category": p.product_category,
            "offering_type": p.offering_type,
            "variant_name": p.variant_name,
            "sku": p.sku,
            "pack_size": float(p.pack_size) if p.pack_size is not None else None,
            "pack_unit": p.pack_unit,
            "ingredients": p.ingredients_components,
            "market": p.applicable_market,
            "status": p.record_status
        }
        for p in products
    ]
    claims_snapshot = [
        {
            "claim_id": c.claim_id,
            "applicable_product_id": c.applicable_product_id,
            "claim_text": c.claim_text,
            "status": c.claim_status,
            "type": c.claim_type,
            "restricted_conditions": c.restricted_conditions,
            "prohibited_variations": c.prohibited_variations,
            "approved_variations": c.approved_variations,
            "market": c.applicable_market,
            "effective_from": str(c.effective_from) if c.effective_from else None,
            "effective_until": str(c.effective_until) if c.effective_until else None
        }
        for c in claims
    ]
    rules_snapshot = [
        {
            "id": r.id,
            "rule_code": r.rule_code,

            "rule_type": r.rule_type,
            "severity": r.severity,
            "title": r.title,
            "explanation": r.explanation,
            "pattern": r.pattern,
            "examples_good": r.examples_good,
            "examples_bad": r.examples_bad,
            "source_citation": r.source_citation,
            "scope": r.scope,
            "status": r.status,
            "brand_id": r.brand_id,
            "recommended_alternatives": getattr(r, "recommended_alternatives", None)
        }
        for r in rules
    ]
    facts_snapshot = [
        {
            "id": f.id,
            "product_id": f.product_id,
            "category": f.category,
            "product_name": f.product_name,
            "fact_key": f.fact_key,
            "fact_value": f.fact_value,
            "status": f.status,
            "valid_from": str(f.valid_from) if f.valid_from else None,
            "valid_until": str(f.valid_until) if f.valid_until else None,
            "source_citation": f.source_citation,
            "brand_id": f.brand_id
        }
        for f in facts
    ]
    disclosures_snapshot = [
        {
            "disclosure_id": d.disclosure_id,
            "applicable_product_id": d.applicable_product_id,
            "text": d.disclosure_text,
            "applies_when": d.applies_when,
            "applicable_market": d.applicable_market,
            "effective_from": str(d.effective_from) if d.effective_from else None,
            "effective_until": str(d.effective_until) if d.effective_until else None
        }
        for d in disclosures
    ]
    assets_snapshot = [
        {
            "asset_id": a.id,
            "asset_name": a.asset_name,
            "asset_type": a.asset_type,
            "file_path": a.file_path,
            "status": a.status
        }
        for a in assets
    ]

    manifest_dict = {
        "version_num": next_version,
        "organization_id": org_id,
        "brand_profile": {
            "brand_name": brand_profile.brand_name,
            "description": brand_profile.brand_description,
            "personality": brand_profile.brand_personality or [],
            "preferred_tone": brand_profile.preferred_tone or [],
            "tones_to_avoid": brand_profile.tones_to_avoid or [],
            "preferred_terminology": brand_profile.preferred_terminology or [],
            "prohibited_terminology": brand_profile.prohibited_terminology or [],
            "writing_style": brand_profile.writing_style,
            "spelling_convention": brand_profile.spelling_convention,
            "writing_style_instructions": brand_profile.writing_style_instructions,
            "approved_languages": brand_profile.approved_languages or [],
            "heading_font": brand_profile.primary_heading_font,
            "body_font": brand_profile.secondary_body_font,
            "additional_fonts": brand_profile.additional_approved_fonts or [],
            "visual_style": brand_profile.visual_style or [],
            "imagery_style": brand_profile.preferred_imagery_style or [],
            "backgrounds": brand_profile.preferred_backgrounds or [],
            "preferred_visual_treatments": brand_profile.preferred_visual_treatments or [],
            "visual_styles_to_avoid": brand_profile.visual_styles_to_avoid or [],
            "logo_instructions": brand_profile.logo_usage_instructions,
        },
        "brand_colors": colors_snapshot,
        "products": products_snapshot,
        "claims": claims_snapshot,
        "required_disclosures": disclosures_snapshot,
        "brand_assets": assets_snapshot,
        "rules": rules_snapshot,
        "facts": facts_snapshot,
        "activated_at": datetime.utcnow().isoformat(),
        "activated_by": current_user.id
    }

    manifest_json = json.dumps(manifest_dict, sort_keys=True, default=str)
    manifest_sha256 = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

    reason = payload.activation_reason if (payload and payload.activation_reason) else f"Activated knowledge base v{next_version}"

    # 1. Create Immutable KnowledgeBaseVersion
    kb_ver = KnowledgeBaseVersion(
        organization_id=org_id,
        version_num=next_version,
        manifest_sha256=manifest_sha256,
        manifest_data=manifest_dict,
        activated_by=current_user.id,
        activation_reason=reason
    )
    db.add(kb_ver)
    db.flush()

    # 2. Update Active Pointer
    active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
        OrganizationActiveKnowledgeBase.organization_id == org_id
    ).first()

    if not active_kb:
        active_kb = OrganizationActiveKnowledgeBase(
            organization_id=org_id,
            active_version_id=kb_ver.id,
            activated_by=current_user.id,
            activated_at=datetime.utcnow()
        )
        db.add(active_kb)
    else:
        active_kb.active_version_id = kb_ver.id
        active_kb.activated_by = current_user.id
        active_kb.activated_at = datetime.utcnow()

    db.commit()
    db.refresh(kb_ver)

    log_audit_event(
        db=db,
        organization_id=org_id,
        user_id=current_user.id,
        event_type="KNOWLEDGE_BASE_ACTIVATED",
        entity_type="knowledge_base_version",
        entity_id=kb_ver.id,
        summary=f"Activated Knowledge Base Version {kb_ver.version_num} (SHA-256: {manifest_sha256[:16]}...)",
        details={
            "version_num": kb_ver.version_num,
            "manifest_sha256": manifest_sha256,
            "reason": reason,
            "products_count": len(products),
            "claims_count": len(claims),
            "disclosures_count": len(disclosures)
        }
    )

    # 3. Trigger Bounded Synchronous Impact Re-Scoring over active drafts
    try:
        rescore_job = rescore_service.trigger_rescore_for_activation(
            db=db,
            org_id=org_id,
            kb_version=kb_ver,
            user_id=current_user.id
        )
    except Exception as rescore_err:
        logger.error(f"Synchronous rescoring encountered an unexpected error: {rescore_err}")
        rescore_job = None

    return KnowledgeBaseActivationOut(
        version_id=kb_ver.id,
        version_num=kb_ver.version_num,
        manifest_sha256=manifest_sha256,
        activation_reason=reason,
        activated_at=kb_ver.activated_at,
        activated_by=current_user.id,
        counts={
            "colors": len(colors),
            "products": len(products),
            "claims": len(claims),
            "required_disclosures": len(disclosures),
            "assets": len(assets)
        },
        rescore_job_id=rescore_job.id if rescore_job else None,
        rescore_summary={
            "total_items": rescore_job.total_items if rescore_job else 0,
            "completed_items": rescore_job.completed_items if rescore_job else 0,
            "status": rescore_job.status if rescore_job else "none"
        } if rescore_job else None
    )


# -----------------------------------------------------------------------------
# PRODUCTS, CLAIMS, DISCLOSURES & RESCORE QUERY ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/products")
def get_products(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """Returns all active catalogue products for the user's organization."""
    return db.query(Product).filter(
        Product.organization_id == membership.organization_id
    ).order_by(Product.product_name.asc()).all()


@router.get("/claims")
def get_claims(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """Returns all claims for the user's organization."""
    return db.query(Claim).filter(
        Claim.organization_id == membership.organization_id
    ).order_by(Claim.claim_id.asc()).all()


@router.get("/disclosures")
def get_disclosures(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """Returns all required disclosures for the user's organization."""
    return db.query(RequiredDisclosure).filter(
        RequiredDisclosure.organization_id == membership.organization_id
    ).order_by(RequiredDisclosure.disclosure_id.asc()).all()


@router.get("/rescore-jobs")
def list_rescore_jobs(
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    db: Session = Depends(get_db)
):
    """Returns recent guideline update impact re-scoring jobs."""
    return rescore_service.list_jobs(db, membership.organization_id)


@router.get("/rescore-jobs/{job_id}")
def get_rescore_job_detail(
    job_id: str,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    db: Session = Depends(get_db)
):
    """Returns detailed item-level impact re-scoring summary."""
    summary = rescore_service.get_job_summary(db, membership.organization_id, job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Rescore job not found")
    return summary


@router.post("/live-check", response_model=LiveCheckResponse)
def live_check_content(
    req: LiveCheckRequest,
    membership: OrganizationMembership = Depends(require_content_creator),
    db: Session = Depends(get_db)
):
    """
    Round 2 Commitment 1 / Round 3 P0-3: Debounced In-Editor Real-Time Assistant.
    Evaluates in-progress copy against approved rules and claims without creating a version or run.
    Returns inline infractions with actionable one-click auto-fix proposals.
    """
    org_id = membership.organization_id
    text = (req.body_text or "").strip()
    if not text:
        return LiveCheckResponse(status="clean", infractions=[], total_infractions=0)

    resolved_kb = resolve_knowledge_base(db, org_id)
    rules = resolved_kb.rules
    profile = resolved_kb.brand_profile
    brand_name = profile.brand_name if profile else "Brand"
    claims = resolved_kb.claims
    disclosures = resolved_kb.required_disclosures

    infractions: List[LiveInfraction] = []

    # Check Rules
    for rule in rules:
        if not rule.pattern:
            continue
        patterns = [p.strip() for p in rule.pattern.replace("|", ",").split(",") if p.strip()]
        for pat in patterns:
            idx = text.lower().find(pat.lower())
            if idx != -1:
                matched_span = text[idx : idx + len(pat)]
                replacement = None
                can_fix = False
                if rule.recommended_alternatives:
                    replacement = rule.recommended_alternatives.split(",")[0].strip()
                    can_fix = True
                elif "Freshsip Pvt" in pat or "Pvt. Ltd." in pat:
                    replacement = brand_name
                    can_fix = True

                infractions.append(LiveInfraction(
                    id=str(uuid.uuid4()),
                    rule_code=rule.rule_code,
                    category=rule.rule_type or "rule_violation",
                    severity=rule.severity,
                    title=rule.title,
                    explanation=rule.explanation or f"Matches prohibited term '{pat}'",
                    matched_text=matched_span,
                    replacement_text=replacement,
                    can_autofix=can_fix
                ))
                break

    # Check Claims Prohibited Variations
    for clm in claims:
        if clm.claim_status == "Prohibited":
            if clm.claim_text and clm.claim_text.lower() in text.lower():
                infractions.append(LiveInfraction(
                    id=str(uuid.uuid4()),
                    rule_code=clm.claim_id,
                    category="prohibited_claim",
                    severity="error",
                    title=f"Prohibited Claim Detected ({clm.claim_id})",
                    explanation=f"Claim '{clm.claim_text}' is prohibited under active governance guidelines.",
                    matched_text=clm.claim_text,
                    replacement_text=None,
                    can_autofix=False
                ))
        if clm.prohibited_variations:
            for pvar in clm.prohibited_variations.split(","):
                pvar = pvar.strip()
                if pvar and pvar.lower() in text.lower():
                    infractions.append(LiveInfraction(
                        id=str(uuid.uuid4()),
                        rule_code=clm.claim_id,
                        category="unsubstantiated_claim",
                        severity="error",
                        title=f"Disallowed Claim Variation ({clm.claim_id})",
                        explanation=f"Phrasing '{pvar}' is explicitly disallowed.",
                        matched_text=pvar,
                        replacement_text=clm.approved_variations.split(",")[0].strip() if clm.approved_variations else None,
                        can_autofix=bool(clm.approved_variations)
                    ))
                    break

    # Check Required Disclosures for selected product or ALL
    prod_code = None
    if req.product_id:
        selected_prod = None
        for p in resolved_kb.products:
            if getattr(p, "id", None) == req.product_id or getattr(p, "product_id", None) == req.product_id:
                selected_prod = p
                break
        if not selected_prod and resolved_kb.baseline_status == "legacy_unversioned":
            selected_prod = db.query(Product).filter(
                Product.organization_id == org_id,
                Product.id == req.product_id
            ).first()
        if selected_prod:
            prod_code = getattr(selected_prod, "product_id", None)

    for disc in disclosures:
        if disc.applicable_product_id in ("ALL", prod_code):
            if disc.disclosure_text and disc.disclosure_text.lower() not in text.lower():
                infractions.append(LiveInfraction(
                    id=str(uuid.uuid4()),
                    rule_code=disc.disclosure_id,
                    category="missing_mandatory_disclosure",
                    severity="warning",
                    title=f"Missing Disclosure: {disc.disclosure_id}",
                    explanation=f"Required disclosure for {disc.applicable_product_id}: '{disc.disclosure_text}'",
                    matched_text=None,
                    replacement_text=f"{text}\n\n{disc.disclosure_text}" if text else disc.disclosure_text,
                    can_autofix=True
                ))

    return LiveCheckResponse(
        status="violations_detected" if infractions else "clean",
        infractions=infractions,
        total_infractions=len(infractions)
    )


class RescoreTriggerRequest(BaseModel):
    knowledge_base_version_id: Optional[str] = None
    scope: Optional[str] = "all"
    channel: Optional[str] = None


@router.post("/rescore-trigger")
def trigger_rescore_job(
    req: RescoreTriggerRequest,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Round 2 Commitment 3 / Round 3 P0-2: Trigger Guideline Impact Rescoring Hub Simulation.
    Evaluates historical content items against the specified (or active) Knowledge Base Version
    in shadow mode with immutable audit trail.
    """
    org_id = membership.organization_id
    kb_ver = None
    if req.knowledge_base_version_id:
        kb_ver = db.query(KnowledgeBaseVersion).filter(
            KnowledgeBaseVersion.id == req.knowledge_base_version_id,
            KnowledgeBaseVersion.organization_id == org_id
        ).first()
    if not kb_ver:
        active = db.query(OrganizationActiveKnowledgeBase).filter(
            OrganizationActiveKnowledgeBase.organization_id == org_id
        ).first()
        if active and active.active_version_id:
            kb_ver = db.query(KnowledgeBaseVersion).filter(
                KnowledgeBaseVersion.id == active.active_version_id
            ).first()

    if not kb_ver:
        kb_ver = db.query(KnowledgeBaseVersion).filter(
            KnowledgeBaseVersion.organization_id == org_id
        ).order_by(KnowledgeBaseVersion.version_num.desc()).first()

    if not kb_ver:
        raise HTTPException(status_code=400, detail="No active or historical knowledge base version found to rescore against.")

    job = rescore_service.trigger_rescore_for_activation(
        db=db,
        org_id=org_id,
        kb_version=kb_ver,
        user_id=current_user.id
    )

    return {
        "status": "success",
        "job_id": job.id,
        "version_num": kb_ver.version_num,
        "total_items": job.total_items,
        "completed_items": job.completed_items,
        "job_status": job.status
    }


@router.get("/versions")
def get_kb_versions(
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    db: Session = Depends(get_db)
):
    """Returns all immutable knowledge base versions and manifests for the organization."""
    return db.query(KnowledgeBaseVersion).filter(
        KnowledgeBaseVersion.organization_id == membership.organization_id
    ).order_by(KnowledgeBaseVersion.version_num.desc()).all()


@router.delete("/assets/{asset_id}")
def delete_brand_asset(
    asset_id: str,
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    db: Session = Depends(get_db)
):
    """Deletes a brand asset."""
    asset = db.query(BrandAsset).filter(
        BrandAsset.id == asset_id,
        BrandAsset.organization_id == membership.organization_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    db.delete(asset)
    db.commit()
    return {"message": "Asset deleted successfully."}


@router.get("/sources/{source_id}/download")
def download_knowledge_source(
    source_id: str,
    token: Optional[str] = None,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """Downloads or streams an uploaded knowledge source file."""
    actual_token = auth_credentials.credentials if auth_credentials else token
    if not actual_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    payload = decode_access_token(actual_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if not source or not source.file_path:
        raise HTTPException(status_code=404, detail="Source not found.")

    if not storage_service.check_exists(source.file_path):
        raise HTTPException(status_code=404, detail="Source file not found on disk.")

    local_path = storage_service.get_file_path_for_processing(source.file_path)
    return FileResponse(
        local_path,
        media_type=source.mime_type or "application/octet-stream",
        filename=source.filename
    )


@router.get("/imports")
def list_staged_imports(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """Lists historical and active Excel imports for the organization."""
    imports = db.query(StagedImport).filter(
        StagedImport.organization_id == membership.organization_id
    ).order_by(StagedImport.created_at.desc()).all()

    results = []
    for imp in imports:
        creator_name = imp.creator.full_name if (imp.creator and imp.creator.full_name) else (imp.creator.email if imp.creator else "System")
        results.append({
            "id": imp.id,
            "organization_id": imp.organization_id,
            "import_type": imp.import_type,
            "file_name": imp.file_name,
            "status": imp.status,
            "total_rows": imp.total_rows,
            "valid_rows": imp.valid_rows,
            "error_rows": imp.error_rows,
            "has_disclosures": imp.has_disclosures,
            "created_by": imp.created_by,
            "created_by_name": creator_name,
            "created_at": imp.created_at.isoformat() if imp.created_at else None,
            "expires_at": imp.expires_at.isoformat() if imp.expires_at else None,
        })
    return results
