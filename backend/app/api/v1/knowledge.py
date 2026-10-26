import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership, User
from app.models.knowledge import KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset
from app.models.brand import Brand
from app.schemas.knowledge import (
    KnowledgeSourceOut,
    KnowledgeRuleOut, KnowledgeRuleCreate, KnowledgeRuleReview,
    KnowledgeFactOut, KnowledgeFactCreate, KnowledgeFactReview,
    BrandAssetOut, BrandAssetReview
)
from app.services.storage import storage_service
from app.services.extraction import extract_pdf_text_and_candidates, extract_image_metadata
from app.services.audit import log_audit_event
from app.api.deps import get_current_user, require_any_member, require_knowledge_reviewer

router = APIRouter()

@router.post("/upload", response_model=KnowledgeSourceOut)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: str = Form(...),
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

    # Create KnowledgeSource record in pending_review
    source = KnowledgeSource(
        organization_id=org_id,
        brand_id=brand_id,
        title=title,
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

    # Extract based on file type
    if file.content_type == "application/pdf" or safe_filename.lower().endswith(".pdf"):
        summary, candidate_rules, candidate_facts = extract_pdf_text_and_candidates(file_path, safe_filename)
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
                source_citation=r["source_citation"],
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
                supporting_evidence=f["supporting_evidence"],
                source_citation=f["source_citation"],
                status="pending_review"  # Starts in pending_review
            )
            db.add(fact_obj)
            facts_created += 1

    elif file.content_type and file.content_type.startswith("image/"):
        meta = extract_image_metadata(file_path, safe_filename)
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

    db.commit()
    db.refresh(source)

    # Log structured audit event
    log_audit_event(
        db=db,
        organization_id=org_id,
        user_id=current_user.id,
        event_type="KNOWLEDGE_UPLOADED",
        entity_type="knowledge_source",
        entity_id=source.id,
        summary=f"Uploaded {source_type} '{title}' ({safe_filename}). Created candidate records.",
        details={
            "rules_candidate_count": rules_created,
            "facts_candidate_count": facts_created,
            "assets_candidate_count": assets_created,
            "status": "pending_review"
        }
    )

    out = KnowledgeSourceOut.from_orm(source)
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
        
        out = KnowledgeSourceOut.from_orm(s)
        out.rules_count = r_cnt
        out.facts_count = f_cnt
        out.assets_count = a_cnt
        result.append(out)

    return result


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
        details={"notes": req.review_notes}
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
        valid_from=req.valid_from,
        valid_until=req.valid_until,
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
        details={"notes": req.review_notes}
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
