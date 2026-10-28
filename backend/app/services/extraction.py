"""
Knowledge Extraction Service for Inkloom AI.

Production implementation powered by Gemini 3.8 Flash structured extraction
with evidence verification against source PDF pages.
"""

import os
import re
import json
import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image

from app.services.gemini_extractor import run_gemini_pdf_extraction, GeminiConfigurationError, GeminiExtractionError
from app.services.evidence_validator import (
    extract_pdf_pages,
    extract_rule_traceability_matrix,
    validate_candidate_evidence,
    validate_fact_consistency,
    validate_rule_consistency,
    normalize_text
)

logger = logging.getLogger(__name__)


def select_best_rule_evidence_passage(
    passages: List[str],
    statement: str = "",
    title: str = ""
) -> Optional[str]:
    """
    Selects the best supporting evidence passage representing the substantive rule requirement.
    Avoids choosing administrative review/status commentary (e.g. 'Status: pending_review...')
    when substantive requirement text is available.
    """
    if not passages:
        return None
    if len(passages) == 1:
        return passages[0]

    administrative_prefixes = (
        "status: pending_review",
        "status: approved",
        "status: expired",
        "status: rejected",
        "candidate rule awaiting",
        "retained in brand_rules",
        "approval_status ="
    )

    substantive_passages = [
        p for p in passages
        if not any(normalize_text(p).startswith(prefix) for prefix in administrative_prefixes)
    ]

    if substantive_passages:
        if statement:
            norm_stmt = normalize_text(statement)
            for sp in substantive_passages:
                norm_sp = normalize_text(sp)
                shared_words = [w for w in norm_stmt.split() if len(w) > 4 and w in norm_sp]
                if len(shared_words) >= 2:
                    return sp
        return substantive_passages[0]

    return passages[0]


def extract_pdf_text_and_candidates(
    file_path: str,
    filename: str
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extracts structured brand governance rules, product facts, claims, and asset policies
    from a brand guideline PDF using Gemini with strict local schema validation.
    
    CRITICAL REQUIREMENTS:
    1. ALL extracted rules and facts start in status='pending_review'.
    2. Preserves source_status separately from review_status.
    3. Grounded in source passages with evidence validation against actual PDF pages.
    4. Distinguishes stated facts from data gaps (missing_not_provided).
    5. Excludes non-governance elements (disclaimers, demographics, examples).
    6. Does NOT silently fall back to regex on failure; raises clear exception.
    7. Separates deterministic matrix metadata from semantic interpretation.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    t_total_start = time.perf_counter()

    # 1. Extract raw page text from PDF and parse deterministic Rule Traceability Matrix
    t_pdf_start = time.perf_counter()
    pdf_pages = extract_pdf_pages(file_path)
    total_pdf_pages = len(pdf_pages)
    full_pdf_text = "\n".join(pdf_pages)
    known_matrix = extract_rule_traceability_matrix(pdf_pages)
    pdf_parsing_ms = round((time.perf_counter() - t_pdf_start) * 1000, 2)
    logger.info(
        f"PDF parsed in {pdf_parsing_ms}ms ({total_pdf_pages} pages). "
        f"Found {len(known_matrix)} deterministic rule matrix entries."
    )

    # 2. Execute single structured Gemini extraction request
    logger.info(f"Initiating single Gemini structured extraction on '{filename}' ({total_pdf_pages} pages)...")
    extracted_doc, gemini_timings = run_gemini_pdf_extraction(file_path, filename, known_matrix=known_matrix)

    candidate_rules: List[Dict[str, Any]] = []
    candidate_facts: List[Dict[str, Any]] = []

    t_ev_start = time.perf_counter()

    # 3. Process Brand Rules
    for r in extracted_doc.brand_rules:
        # Validate supporting passage against document pages
        ev_res = validate_candidate_evidence(r.supporting_passages, r.source_page_numbers, pdf_pages)
        primary_page = r.source_page_numbers[0] if r.source_page_numbers else 1
        page_text = pdf_pages[primary_page - 1] if 1 <= primary_page <= len(pdf_pages) else ""

        # Deterministic matrix lookup
        base_match = re.match(r'^(FR-RULE-\d{3})', r.rule_id, re.IGNORECASE)
        base_code = base_match.group(1).upper() if base_match else r.rule_id.upper()
        mat_meta = known_matrix.get(base_code, {})

        effective_title = mat_meta.get("title") or r.title
        effective_cat = mat_meta.get("category") or r.category or "other"
        effective_type = mat_meta.get("rule_type") or r.rule_type or "guideline"
        effective_sev = mat_meta.get("severity") or r.severity
        effective_act = mat_meta.get("enforcement_action") or r.enforcement_action
        effective_stat = mat_meta.get("source_status") or r.source_status or "unknown"

        # Handle ambiguous, missing, or unparsed metadata without silent guessing
        metadata_ambiguity_note = None
        if not effective_sev:
            effective_sev = "warning"
            metadata_ambiguity_note = "METADATA_AMBIGUITY: Severity was not deterministically found in source matrix or text; assigned 'warning' pending reviewer classification."
        if not effective_act:
            effective_act = "flag_for_review"

        # Validate rule metadata consistency against scoped rule entry or traceability matrix
        rule_cons_status, rule_cons_note = validate_rule_consistency(
            rule_id=r.rule_id,
            severity=effective_sev,
            enforcement_action=effective_act,
            supporting_passages=r.supporting_passages,
            page_text=page_text,
            document_text=full_pdf_text,
            known_matrix=known_matrix
        )
        
        # Format pattern/keywords for governance engine matching
        pattern_str = ", ".join(r.pattern_or_keywords) if r.pattern_or_keywords else effective_title

        # Map rule type to governance engine taxonomy
        mapped_rule_type = "prohibited_word" if effective_type == "prohibition" else (
            "required_term" if effective_type == "requirement" else (
                "prohibited_word" if effective_type == "restriction" else effective_type
            )
        )

        # Preserve canonical severities without altering "medium" or "high"
        canonical_sev = effective_sev.lower() if effective_sev and effective_sev.lower() in ("critical", "high", "medium", "low") else "warning"

        final_val_status = ev_res.validation_status
        uncertainty = r.uncertainty_notes or metadata_ambiguity_note or (ev_res.notes if ev_res.validation_status != "verified_exact" else None)
        if rule_cons_status != "consistent" and rule_cons_note:
            final_val_status = "metadata_conflict"
            uncertainty = f"GROUNDING ALERT: {rule_cons_note} - Reviewer verification required."

        chosen_rule_passage = select_best_rule_evidence_passage(
            r.supporting_passages,
            statement=r.statement,
            title=effective_title
        )

        rule_dict = {
            "rule_code": r.rule_id,
            "title": effective_title,
            "pattern": pattern_str,
            "explanation": r.statement,
            "severity": canonical_sev,
            "rule_type": mapped_rule_type,
            "context_condition": r.context_condition,
            "source_citation": f"{filename}, Page {primary_page}",
            "source_status": effective_stat,
            "status": "pending_review",  # CRITICAL: Always pending_review inside Inkloom AI
            "enforcement_action": effective_act,
            "rationale": r.rationale or f"Governance rule established under {base_code}.",
            "recommended_alternatives": json.dumps(r.recommended_alternatives) if r.recommended_alternatives else None,
            "exceptions": json.dumps(r.exceptions) if r.exceptions else None,
            "examples_bad": json.dumps(r.examples_bad) if r.examples_bad else None,
            "examples_good": json.dumps(r.examples_good) if r.examples_good else None,
            "evidence_passage": chosen_rule_passage,
            "page_number": primary_page,
            "evidence_validation": final_val_status,
            "uncertainty_notes": uncertainty,
            "original_extraction": r.model_dump_json(),
            "is_corrected": False
        }
        candidate_rules.append(rule_dict)

    # 4. Process Brand Asset Policies as Rules
    # Disambiguate identifiers so asset policies governed by FR-RULE-017 do not create duplicate canonical keys
    for idx, a in enumerate(extracted_doc.asset_policies, 1):
        ev_res = validate_candidate_evidence(a.supporting_passages, a.source_page_numbers, pdf_pages)
        primary_page = a.source_page_numbers[0] if a.source_page_numbers else 1

        parent_code = a.policy_id or "FR-RULE-017"
        unique_policy_code = f"{parent_code}-AP{idx:02d}"

        parent_meta = known_matrix.get(parent_code, {})
        policy_sev = parent_meta.get("severity", "high")
        policy_act = parent_meta.get("enforcement_action", "block")
        policy_stat = parent_meta.get("source_status", a.source_status)

        chosen_asset_passage = select_best_rule_evidence_passage(
            a.supporting_passages,
            statement=a.policy_statement,
            title=a.asset_target
        )

        asset_rule_dict = {
            "rule_code": unique_policy_code,
            "title": f"Asset Policy: {a.asset_target} ({parent_code})",
            "pattern": a.asset_target,
            "explanation": a.policy_statement,
            "severity": policy_sev,
            "rule_type": "image_standard",
            "context_condition": f"Permitted channels: {', '.join(a.permitted_channels)}" if a.permitted_channels else None,
            "source_citation": f"{filename}, Page {primary_page} ({parent_code})",
            "source_status": policy_stat,
            "status": "pending_review",
            "enforcement_action": policy_act,
            "rationale": f"Governed under {parent_code}. {a.approval_requirement}",
            "recommended_alternatives": None,
            "exceptions": None,
            "examples_bad": None,
            "examples_good": None,
            "evidence_passage": chosen_asset_passage,
            "page_number": primary_page,
            "evidence_validation": ev_res.validation_status,
            "uncertainty_notes": ev_res.notes if ev_res.validation_status != "verified_exact" else None,
            "original_extraction": a.model_dump_json(),
            "is_corrected": False
        }
        candidate_rules.append(asset_rule_dict)

    # 5. Process Product Facts
    for f in extracted_doc.product_facts:
        ev_res = validate_candidate_evidence([f.supporting_evidence], f.source_page_numbers, pdf_pages)
        primary_page = f.source_page_numbers[0] if f.source_page_numbers else 1
        page_text = pdf_pages[primary_page - 1] if 1 <= primary_page <= len(pdf_pages) else ""

        # Validate numeric and semantic consistency against evidence passage and page text
        fact_cons_status, fact_cons_note = validate_fact_consistency(
            value=f.value,
            unit=f.unit,
            supporting_evidence=f.supporting_evidence,
            page_text=page_text
        )

        # Format fact value with unit if provided
        formatted_val = f"{f.value} {f.unit}".strip() if f.unit and not f.value.endswith(f.unit) else f.value

        # Categorize fact for Inkloom taxonomy
        attr_lower = f.attribute.lower()
        if any(term in attr_lower for term in ("sugar", "calorie", "energy", "sodium", "fat", "protein", "carb")):
            cat = "nutrition"
        elif any(term in attr_lower for term in ("allergen", "celery", "salt", "cross_contact")):
            cat = "ingredient"
        elif any(term in attr_lower for term in ("price", "mrp", "cost")):
            cat = "pricing"
        elif any(term in attr_lower for term in ("pack", "size", "material", "bottle", "shelf")):
            cat = "specification"
        else:
            cat = "specification"

        final_val_status = ev_res.validation_status
        uncertainty_note = None

        if fact_cons_status in ("unsupported_value", "contradiction"):
            final_val_status = "unsupported"
            uncertainty_note = f"CONTRADICTION ALERT: {fact_cons_note} - Flagged for mandatory reviewer inspection; cannot be approved as established fact."
        elif f.value_status == "missing_not_provided":
            uncertainty_note = "DATA GAP: Attribute explicitly marked not_provided in specification; requires human review."
        elif f.external_reference_needed:
            uncertainty_note = f"EXTERNAL REF: Referenced external document '{f.external_reference_needed}' not supplied."
        elif ev_res.validation_status != "verified_exact":
            uncertainty_note = ev_res.notes

        fact_dict = {
            "product_id": f.product_id,
            "product_name": f.product_name,
            "category": cat,
            "fact_key": f.attribute,
            "fact_value": formatted_val,
            "unit": f.unit,
            "value_status": f.value_status,
            "source_status": f.source_status,
            "status": "pending_review",
            "page_number": primary_page,
            "source_citation": f"{filename}, Page {primary_page}",
            "supporting_evidence": f.supporting_evidence,
            "evidence_validation": final_val_status,
            "uncertainty_notes": uncertainty_note,
            "original_extraction": f.model_dump_json(),
            "is_corrected": False
        }
        candidate_facts.append(fact_dict)

    # 6. Process Claims as Governance Facts
    for c in extracted_doc.claims:
        ev_res = validate_candidate_evidence(c.supporting_passages, c.source_page_numbers, pdf_pages)
        primary_page = c.source_page_numbers[0] if c.source_page_numbers else 1

        claim_cat = c.claim_category
        # Protect against misclassifying allergen disclosures as health_disease
        if claim_cat in ("health_disease", "other") and any(
            term in (c.claim_text + " " + c.evidence_or_rationale).lower()
            for term in ("allergen", "celery", "cross-contact", "cross_contact", "food safety", "food_safety")
        ):
            claim_cat = "allergen_food_safety"

        claim_dict = {
            "product_id": c.claim_id,
            "product_name": "Freshsip Claims Matrix",
            "category": "claim",
            "fact_key": f"Claim: {claim_cat.replace('_', ' ').title()}",
            "fact_value": f"[{c.decision.upper()}] {c.claim_text}",
            "unit": None,
            "value_status": "explicitly_stated",
            "source_status": c.source_status,
            "status": "pending_review",
            "page_number": primary_page,
            "source_citation": f"{filename}, Page {primary_page}",
            "supporting_evidence": c.evidence_or_rationale,
            "evidence_validation": ev_res.validation_status,
            "uncertainty_notes": (
                f"Candidate claim status '{c.source_status}' / decision '{c.decision}'; requires human reviewer sign-off."
                if c.source_status != "approved" else None
            ),
            "original_extraction": c.model_dump_json(),
            "is_corrected": False
        }
        candidate_facts.append(claim_dict)

    # 7. Build Summary from Document Metadata
    meta = extracted_doc.document_metadata
    exclusions_count = len(meta.non_governance_elements)
    summary = (
        f"Document: {meta.document_title} (ID: {meta.document_id or 'N/A'}, v{meta.version or '1.0'}). "
        f"Extracted {len(candidate_rules)} candidate rules, {len(candidate_facts)} specifications & claims. "
        f"Identified and excluded {exclusions_count} non-governance text elements. "
        f"All records start in pending_review."
    )

    evidence_validation_ms = round((time.perf_counter() - t_ev_start) * 1000, 2)
    total_elapsed_ms = round((time.perf_counter() - t_total_start) * 1000, 2)

    timings: Dict[str, Any] = {
        "event": "extraction_timing",
        "filename": filename,
        "pdf_parsing_ms": pdf_parsing_ms,
        "gemini_upload_ms": gemini_timings.get("upload_duration_ms", 0.0),
        "gemini_generation_ms": gemini_timings.get("generation_duration_ms", 0.0),
        "input_tokens": gemini_timings.get("input_tokens"),
        "output_tokens": gemini_timings.get("output_tokens"),
        "response_parsing_validation_ms": gemini_timings.get("parse_duration_ms", 0.0),
        "evidence_validation_ms": evidence_validation_ms,
        "total_elapsed_ms": total_elapsed_ms,
        "retry_count": gemini_timings.get("retry_count", 0),
        "outcome": "success"
    }

    return summary, candidate_rules, candidate_facts, timings



def extract_image_metadata(file_path: str, filename: str) -> Dict[str, Any]:
    """
    Extracts image dimensions, color mode, aspect ratio, and checks compliance.
    """
    if not os.path.exists(file_path):
        try:
            from app.services.storage import storage_service
            if storage_service.check_exists(file_path):
                file_path = storage_service.get_file_path_for_processing(file_path)
        except Exception:
            pass

    if not os.path.exists(file_path):
        return {}

    try:
        with Image.open(file_path) as img:
            width, height = img.size
            mode = img.mode
            format_name = img.format or "UNKNOWN"
            
            # Aspect ratio normalization
            gcd_val = _gcd(width, height) if height > 0 else 1
            if gcd_val > 10:
                normalized_ratio = f"{width // gcd_val}:{height // gcd_val}"
            else:
                ratio_float = round(width / max(height, 1), 2)
                normalized_ratio = f"{ratio_float}:1"

            return {
                "asset_name": filename,
                "asset_type": "logo" if "logo" in filename.lower() else ("product_image" if "product" in filename.lower() else "campaign_creative"),
                "file_path": file_path,
                "mime_type": f"image/{format_name.lower()}",
                "width": width,
                "height": height,
                "aspect_ratio": normalized_ratio,
                "color_mode": mode,
                "min_clearance_px": 24 if "logo" in filename.lower() else 16,
                "alt_text_required": True,
                "status": "pending_review",
            }
    except Exception as e:
        return {
            "asset_name": filename,
            "asset_type": "campaign_creative",
            "file_path": file_path,
            "mime_type": "image/unknown",
            "status": "pending_review",
            "error": str(e)
        }

def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a
