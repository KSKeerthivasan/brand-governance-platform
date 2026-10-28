import os
import json
import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.knowledge import KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset
from app.models.brand import Brand
from app.schemas.knowledge import (
    KnowledgeSourceOut,
    KnowledgeRuleOut, KnowledgeRuleCreate, KnowledgeRuleReview, KnowledgeRuleUpdate,
    KnowledgeFactOut, KnowledgeFactCreate, KnowledgeFactReview, KnowledgeFactUpdate,
    BrandAssetOut, BrandAssetReview
)
from app.services.storage import storage_service
from app.services.extraction import extract_pdf_text_and_candidates, extract_image_metadata
from app.services.gemini_extractor import GeminiConfigurationError, GeminiExtractionError
from app.services.audit import log_audit_event
from app.services.auth import decode_access_token
from app.api.deps import get_current_user, require_any_member, require_knowledge_reviewer, security

CATEGORY_TITLE_MAP = {
    "pdf_brand_guidelines": "PDF Brand Guidelines",
    "pdf_product_knowledge": "PDF Product Knowledge & Specs",
    "supporting_doc": "Supporting Evidence Document",
    "brand_asset_image": "Brand Asset / Creative Image",
}

router = APIRouter()


@router.post("/upload", response_model=KnowledgeSourceOut)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: str = Form(...),  # pdf_brand_guidelines, pdf_product_knowledge, supporting_doc, brand_asset_image
    brand_id: Optional[str] = Form(None),
    membership: OrganizationMembership = Depends(require_knowledge_reviewer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Step 2 & 3: Upload brand guidelines, product knowledge, or creative assets.
    CRITICAL REQUIREMENT: Newly uploaded document and extracted records start in PENDING_REVIEW state.
    """
    org_id = membership.organization_id
    
    # Save file securely
    file_path, file_size = await storage_service.save_file(file, org_id, subfolder="knowledge")
    safe_filename = os.path.basename(file.filename or "uploaded_doc")

    # Derive title automatically from category if not provided
    effective_title = (title.strip() if title and title.strip() else None) or CATEGORY_TITLE_MAP.get(
        source_type, source_type.replace("_", " ").title()
    )

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
        try:
            summary, candidate_rules, candidate_facts, extraction_timings = extract_pdf_text_and_candidates(local_path, safe_filename)
        except GeminiConfigurationError as gce:
            db.rollback()
            logger.warning(f"EXTRACTION_STAGE_METRICS: {json.dumps({'event': 'extraction_timing', 'filename': safe_filename, 'outcome': 'failed', 'error': 'GeminiConfigurationError'})}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gemini configuration error: {gce}"
            )
        except GeminiExtractionError as gee:
            db.rollback()
            logger.warning(f"EXTRACTION_STAGE_METRICS: {json.dumps({'event': 'extraction_timing', 'filename': safe_filename, 'outcome': 'failed', 'error': 'GeminiExtractionError'})}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini extraction failed: {gee}"
            )
        except Exception as ex:
            db.rollback()
            logger.warning(f"EXTRACTION_STAGE_METRICS: {json.dumps({'event': 'extraction_timing', 'filename': safe_filename, 'outcome': 'failed', 'error': str(ex)})}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document extraction error: {ex}"
            )

        source.extracted_summary = summary

        for r in candidate_rules:
            rule_obj = KnowledgeRule(
                organization_id=org_id,
                brand_id=brand_id,
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
                status="pending_review"  # Starts in pending_review
            )
            db.add(rule_obj)
            rules_created += 1

        for f in candidate_facts:
            fact_obj = KnowledgeFact(
                organization_id=org_id,
                brand_id=brand_id,
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
                status="pending_review"  # Starts in pending_review
            )
            db.add(fact_obj)
            facts_created += 1

    elif file.content_type and file.content_type.startswith("image/"):
        meta = extract_image_metadata(local_path, safe_filename)
        asset_obj = BrandAsset(
            organization_id=org_id,
            brand_id=brand_id,
            source_id=source.id,
            asset_name=safe_filename,
            asset_type=meta.get("asset_type", "campaign_creative"),
            file_path=file_path,
            mime_type=meta.get("mime_type", file.content_type),
            width=meta.get("width"),
            height=meta.get("height"),
            aspect_ratio=meta.get("aspect_ratio"),
            color_mode=meta.get("color_mode"),
            min_clearance_px=meta.get("min_clearance_px", 20),
            alt_text_required=True,
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

