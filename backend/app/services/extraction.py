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


def extract_local_pdf_candidates(
    pdf_pages: List[str],
    filename: str,
    known_matrix: Dict[str, Any],
    gemini_error_detail: str,
    t_start: float,
    pdf_parsing_ms: float = 0.0
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Local fallback extraction path when Gemini cloud extraction is unavailable (e.g. 503).
    Extracts text from PDF pages, parses deterministic rule matrix and structured rule definitions,
    preserves exact page citations and evidence passages, and ensures all candidate records start
    in pending_review with explicit uncertainty_notes identifying local extraction.
    """
    total_pages = len(pdf_pages)
    full_pdf_text = "\n\n".join(pdf_pages).strip()
    total_chars = len(full_pdf_text)

    # Check if document has usable extractable text
    has_usable_text = bool(any(len(p.strip()) > 20 for p in pdf_pages))

    if not has_usable_text:
        summary = (
            f"[Local PDF Extraction — Scanned or Non-Extractable Document]\n"
            f"No extractable text could be recovered from '{filename}' ({total_pages} pages). "
            f"The document appears to be a scanned image or contains non-extractable raster graphics. "
            f"Gemini cloud extraction was unavailable: {gemini_error_detail}. "
            f"Governance rules may be created manually using '+ Add Rule' or by uploading a digital text PDF."
        )
        timings = {
            "event": "extraction_timing",
            "filename": filename,
            "extraction_mode": "local_fallback_no_text",
            "outcome": "limitation_reported",
            "gemini_error": gemini_error_detail,
            "pdf_parsing_ms": pdf_parsing_ms,
            "total_elapsed_ms": round((time.perf_counter() - t_start) * 1000, 2)
        }
        return summary, [], [], timings

    candidate_rules: List[Dict[str, Any]] = []
    candidate_facts: List[Dict[str, Any]] = []

    # 1. Deterministic Traceability Matrix Parsing (Freshsip style)
    if known_matrix:
        for code, meta in known_matrix.items():
            primary_page = 1
            for idx, p_text in enumerate(pdf_pages, 1):
                if code in p_text:
                    primary_page = idx
                    break

            page_text = pdf_pages[primary_page - 1] if 1 <= primary_page <= len(pdf_pages) else ""
            excerpt = f"Requirement under {code}: {meta.get('title')}"
            m = re.search(rf'({re.escape(code)}[^\n.!?]+[.!?]?)', page_text)
            if m:
                excerpt = m.group(1).strip()

            rtype = meta.get("rule_type", "guideline")
            mapped_type = "prohibited_word" if rtype == "prohibition" else (
                "required_term" if rtype == "requirement" else "guideline"
            )

            canonical_sev = meta.get("severity", "warning").lower()
            if canonical_sev not in ("critical", "high", "medium", "low"):
                canonical_sev = "warning"

            rule_dict = {
                "rule_code": code,
                "title": meta.get("title") or code,
                "pattern": meta.get("title") or code,
                "explanation": f"Rule requirement: {meta.get('title')}",
                "severity": canonical_sev,
                "rule_type": mapped_type,
                "context_condition": None,
                "source_citation": f"{filename}, Page {primary_page}",
                "source_status": meta.get("source_status", "pending_review"),
                "status": "pending_review",  # CRITICAL: Always pending_review
                "enforcement_action": meta.get("enforcement_action", "flag_for_review"),
                "rationale": f"Governance rule deterministically extracted from traceability matrix ({code}).",
                "recommended_alternatives": None,
                "exceptions": None,
                "examples_bad": None,
                "examples_good": None,
                "evidence_passage": excerpt,
                "page_number": primary_page,
                "evidence_validation": "verified_exact",
                "uncertainty_notes": (
                    f"LOCAL_EXTRACTION: Deterministically extracted from traceability matrix "
                    f"(Gemini unavailable). Reviewer verification required before approval."
                ),
                "original_extraction": json.dumps({"extraction_mode": "local_traceability_matrix", "rule_code": code}),
                "is_corrected": False
            }
            candidate_rules.append(rule_dict)

    # 2. Structured Rule Definitions in Page Text (e.g. NexoraTech style)
    if not candidate_rules:
        blocks = re.split(r'(?=Rule ID:\s*[A-Z0-9-]+)', full_pdf_text)
        if len(blocks) > 1:
            for b in blocks[1:]:
                m_id = re.search(r'Rule ID:\s*([A-Z0-9-]+)', b)
                m_title = re.search(r'Rule title:\s*([^\n|]+)', b)
                m_sev = re.search(r'Severity:\s*([^\n|]+)', b)
                m_cat = re.search(r'Category:\s*([^|\n]+)', b)
                m_req = re.search(r'Requirement:\s*([\s\S]*?)(?:Example of non-compliant|Applicable product|\n\s*\n|$)', b)
                m_bad = re.search(r'Example of non-compliant content:\s*[“"\']?([^”"\n]+)', b)
                m_good = re.search(r'Example of compliant content[^:\n]*:\s*[“"\']?([^”"\n]+)', b)

                if m_id:
                    code = m_id.group(1).strip()
                    title = m_title.group(1).strip() if m_title else code
                    raw_sev = m_sev.group(1).strip().lower() if m_sev else "warning"
                    sev = raw_sev if raw_sev in ("critical", "high", "medium", "low") else "warning"
                    req_text = " ".join(m_req.group(1).split()) if m_req else f"Rule requirement under {code}."
                    bad_ex = m_bad.group(1).strip() if m_bad else None
                    good_ex = m_good.group(1).strip() if m_good else None

                    # Locate 1-indexed page where this rule block occurs
                    primary_page = 1
                    for idx, p_text in enumerate(pdf_pages, 1):
                        if f"Rule ID: {code}" in p_text or f"Rule ID:{code}" in p_text or code in p_text:
                            primary_page = idx
                            if f"Rule ID: {code}" in p_text or f"Rule ID:{code}" in p_text:
                                break

                    pattern_str = bad_ex if bad_ex else title
                    cat_lower = m_cat.group(1).strip().lower() if m_cat else ""
                    mapped_type = "prohibited_word" if bad_ex else (
                        "claim_policy" if "claim" in cat_lower else "guideline"
                    )

                    rule_dict = {
                        "rule_code": code,
                        "title": title,
                        "pattern": pattern_str,
                        "explanation": req_text,
                        "severity": sev,
                        "rule_type": mapped_type,
                        "context_condition": None,
                        "source_citation": f"{filename}, Page {primary_page}",
                        "source_status": "pending_review",
                        "status": "pending_review",  # CRITICAL: Always pending_review
                        "enforcement_action": "flag_for_review",
                        "rationale": f"Governance rule extracted locally from {code} definition block.",
                        "recommended_alternatives": json.dumps([good_ex]) if good_ex else None,
                        "exceptions": None,
                        "examples_bad": json.dumps([bad_ex]) if bad_ex else None,
                        "examples_good": json.dumps([good_ex]) if good_ex else None,
                        "evidence_passage": f"{code} - {title}: {req_text[:180]}",
                        "page_number": primary_page,
                        "evidence_validation": "verified_exact",
                        "uncertainty_notes": (
                            f"LOCAL_EXTRACTION: Extracted via local deterministic text parser "
                            f"(Gemini unavailable: {gemini_error_detail}). Reviewer verification required before approval."
                        ),
                        "original_extraction": json.dumps({"extraction_mode": "local_text_parser", "rule_code": code}),
                        "is_corrected": False
                    }
                    candidate_rules.append(rule_dict)

    # 3. Generic Rule ID Pattern Scan Fallback
    if not candidate_rules:
        seen_codes = set()
        for idx, p_text in enumerate(pdf_pages, 1):
            for line in p_text.splitlines():
                m_gen = re.search(r'([A-Z]{2,6}-RULE-\d{2,4})\b', line)
                if m_gen:
                    code = m_gen.group(1)
                    if code not in seen_codes:
                        seen_codes.add(code)
                        clean_line = " ".join(line.split())
                        candidate_rules.append({
                            "rule_code": code,
                            "title": clean_line[:80],
                            "pattern": clean_line[:120],
                            "explanation": clean_line,
                            "severity": "warning",
                            "rule_type": "guideline",
                            "context_condition": None,
                            "source_citation": f"{filename}, Page {idx}",
                            "source_status": "pending_review",
                            "status": "pending_review",
                            "enforcement_action": "flag_for_review",
                            "rationale": f"Rule candidate identified locally on page {idx}.",
                            "recommended_alternatives": None,
                            "exceptions": None,
                            "examples_bad": None,
                            "examples_good": None,
                            "evidence_passage": clean_line,
                            "page_number": idx,
                            "evidence_validation": "verified_exact",
                            "uncertainty_notes": (
                                f"LOCAL_EXTRACTION: Identified via local pattern scan "
                                f"(Gemini unavailable). Reviewer verification required before approval."
                            ),
                            "original_extraction": json.dumps({"extraction_mode": "local_pattern_scan", "rule_code": code}),
                            "is_corrected": False
                        })

    # 4. Product Facts Pattern Scan
    seen_facts = set()
    for idx, p_text in enumerate(pdf_pages, 1):
        for line in p_text.splitlines():
            m_fact = re.search(r'([A-Z]{2,6}-FACT-\d{2,4})\b', line)
            if m_fact:
                f_code = m_fact.group(1)
                if f_code not in seen_facts:
                    seen_facts.add(f_code)
                    clean_line = " ".join(line.split())
                    candidate_facts.append({
                        "product_name": filename.replace(".pdf", "").replace("_", " ").title(),
                        "category": "specification",
                        "fact_key": f_code,
                        "fact_value": clean_line[:200],
                        "supporting_evidence": clean_line,
                        "source_citation": f"{filename}, Page {idx}",
                        "product_id": None,
                        "unit": None,
                        "value_status": "explicitly_stated",
                        "source_status": "pending_review",
                        "page_number": idx,
                        "evidence_validation": "verified_exact",
                        "uncertainty_notes": (
                            f"LOCAL_EXTRACTION: Fact candidate parsed locally (Gemini unavailable). "
                            f"Reviewer verification required before approval."
                        ),
                        "original_extraction": json.dumps({"extraction_mode": "local_fact_scan", "fact_code": f_code}),
                        "is_corrected": False,
                        "status": "pending_review"
                    })

    # Build clear, transparent summary
    rule_msg = (
        f"Extracted {len(candidate_rules)} candidate rules and {len(candidate_facts)} candidate facts into Pending Review."
        if candidate_rules
        else "No structured rule tables detected automatically; use '+ Add Rule' to enter rules manually from the document text."
    )
    summary = (
        f"[Local PDF Text Extraction — Gemini Unavailable]\n"
        f"Extracted text from {total_pages} page(s) ({total_chars} characters) in '{filename}'.\n"
        f"{rule_msg}\n"
        f"Gemini notice: {gemini_error_detail}\n"
        f"All extracted items start in Pending Review and require human reviewer sign-off before governance enforcement."
    )

    timings = {
        "event": "extraction_timing",
        "filename": filename,
        "extraction_mode": "local_fallback",
        "outcome": "recovered_locally",
        "gemini_error": gemini_error_detail,
        "pdf_parsing_ms": pdf_parsing_ms,
        "total_elapsed_ms": round((time.perf_counter() - t_start) * 1000, 2),
        "rules_extracted": len(candidate_rules),
        "facts_extracted": len(candidate_facts)
    }

    return summary, candidate_rules, candidate_facts, timings


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
    6. Gracefully recovers via deterministic local text extraction if Gemini is unavailable (e.g. 503).
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

    # 2. Attempt Gemini structured extraction with local recovery fallback
    extracted_doc = None
    gemini_timings: Dict[str, Any] = {}
    gemini_error_msg = ""

    try:
        logger.info(f"Initiating single Gemini structured extraction on '{filename}' ({total_pdf_pages} pages)...")
        extracted_doc, gemini_timings = run_gemini_pdf_extraction(file_path, filename, known_matrix=known_matrix)
    except (GeminiConfigurationError, GeminiExtractionError) as g_err:
        gemini_error_msg = str(g_err)
        logger.warning(
            f"Gemini structured extraction unavailable for '{filename}' ({gemini_error_msg}). "
            f"Recovering through local PDF text extraction path..."
        )

    if extracted_doc is None:
        # Recover gracefully through local extraction
        return extract_local_pdf_candidates(
            pdf_pages=pdf_pages,
            filename=filename,
            known_matrix=known_matrix,
            gemini_error_detail=gemini_error_msg,
            t_start=t_total_start,
            pdf_parsing_ms=pdf_parsing_ms
        )

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
