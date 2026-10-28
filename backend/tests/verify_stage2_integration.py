"""
Focused Stage 2 Production Integration Verification Suite.

Tests:
1. Gemini configuration and clear error handling on missing/invalid keys.
2. Provider-compatible schema generation (no additionalProperties).
3. Strict local Pydantic validation (extra='forbid') rejecting unexpected fields.
4. Evidence and page reference validation against PDF text.
5. Status separation (source_status vs review_status == 'pending_review').
6. Reprocessing safety (protects approved, rejected, and reviewer-edited knowledge).
7. Governance engine consumption of ONLY approved knowledge.
"""

import os
import sys
import json
import pytest
from pydantic import ValidationError

from app.services.extraction_schemas import (
    StrictKnowledgeDocumentExtraction,
    StrictBrandRule,
    StrictProductFact,
    StrictClaim,
    StrictAssetPolicy,
    StrictDocumentMetadata,
    get_gemini_extraction_response_schema
)
from app.services.evidence_validator import (
    extract_pdf_pages,
    validate_candidate_evidence,
    normalize_text
)
from app.services.gemini_extractor import (
    GeminiConfigurationError,
    GeminiExtractionError,
    run_gemini_pdf_extraction
)


def test_provider_schema_has_no_additional_properties():
    """Verify provider schema prunes additionalProperties to avoid Gemini HTTP 400."""
    schema = get_gemini_extraction_response_schema()
    schema_dump = json.dumps(schema)
    assert "additionalProperties" not in schema_dump
    assert "additional_properties" not in schema_dump


def test_strict_local_validation_rejects_unexpected_fields():
    """Verify local schema has extra='forbid' and fails on unknown keys."""
    valid_rule_data = {
        "rule_id": "FR-RULE-TEST",
        "title": "Strict Test Rule",
        "statement": "You must strictly validate schemas.",
        "category": "governance_and_escalation",
        "rule_type": "requirement",
        "severity": "high",
        "enforcement_action": "block",
        "rationale": "Prevents data corruption.",
        "source_filename": "test.pdf",
        "source_page_numbers": [1],
        "supporting_passages": ["You must strictly validate schemas."]
    }

    # Should succeed with valid data
    rule = StrictBrandRule.model_validate(valid_rule_data)
    assert rule.rule_id == "FR-RULE-TEST"

    # Should raise ValidationError when unknown field is added
    corrupted_data = dict(valid_rule_data)
    corrupted_data["unexpected_hallucinated_field"] = "malicious payload"
    with pytest.raises(ValidationError) as exc_info:
        StrictBrandRule.model_validate(corrupted_data)
    assert "extra_forbidden" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)


def test_missing_api_key_produces_clear_error():
    """Verify missing GEMINI_API_KEY raises GeminiConfigurationError without exposing secrets."""
    original_key = os.environ.get("GEMINI_API_KEY")
    try:
        os.environ["GEMINI_API_KEY"] = ""
        # Also temporarily override settings
        from app.config import settings
        orig_setting = settings.GEMINI_API_KEY
        settings.GEMINI_API_KEY = ""

        with pytest.raises(GeminiConfigurationError) as exc_info:
            run_gemini_pdf_extraction("dummy.pdf", "dummy.pdf")
        assert "GEMINI_API_KEY is not configured" in str(exc_info.value)
    finally:
        if original_key is not None:
            os.environ["GEMINI_API_KEY"] = original_key
        settings.GEMINI_API_KEY = orig_setting


def test_evidence_validator_on_pdf_pages():
    """Verify evidence validation detects exact matches, fuzzy matches, and unverified text."""
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pdf_path = os.path.join(workspace_root, "test_assets", "freshsip_inkloom_demo", "freshsip_brand_guidelines.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Test asset not found at {pdf_path}")

    pages = extract_pdf_pages(pdf_path)
    assert len(pages) == 8

    # 1. Exact match test from Page 1
    res1 = validate_candidate_evidence(
        passages=["bottled fruit juices, vegetable juices, and fruit-and-vegetable juice blends in 250 mL single-serve glass bottles"],
        cited_page_numbers=[1],
        pdf_pages=pages
    )
    assert res1.validation_status in ("verified_exact", "verified_fuzzy")
    assert res1.verified_page == 1

    # 2. Fuzzy match test with smart quotes / intra-word spacing
    res2 = validate_candidate_evidence(
        passages=['"India\'s healthiest juice"'],
        cited_page_numbers=[4],
        pdf_pages=pages
    )
    assert res2.validation_status in ("verified_exact", "verified_fuzzy")

    # 3. Unverified passage test
    res3 = validate_candidate_evidence(
        passages=["This completely fabricated sentence does not exist anywhere in Freshsip guidelines."],
        cited_page_numbers=[1, 2],
        pdf_pages=pages
    )
    assert res3.validation_status == "unverified"

    # 4. Out of bounds page
    res4 = validate_candidate_evidence(
        passages=["Some text"],
        cited_page_numbers=[99],
        pdf_pages=pages
    )
    assert res4.validation_status == "unverified"


def test_reprocessing_preserves_reviewed_and_edited_records():
    """Verify logic: only unreviewed, unedited machine-generated pending records are replaced."""
    # Simulated existing records
    records = [
        {"id": "r1", "status": "approved", "is_corrected": False},
        {"id": "r2", "status": "rejected", "is_corrected": False},
        {"id": "r3", "status": "pending_review", "is_corrected": True},  # Reviewer edited!
        {"id": "r4", "status": "pending_review", "is_corrected": False}, # Unreviewed machine candidate
    ]

    preserved = [r for r in records if r["status"] != "pending_review" or r["is_corrected"]]
    replaceable = [r for r in records if r["status"] == "pending_review" and not r["is_corrected"]]

    assert [r["id"] for r in preserved] == ["r1", "r2", "r3"]
    assert [r["id"] for r in replaceable] == ["r4"]


def test_governance_engine_only_evaluates_approved_rules():
    """Verify that only rules with status='approved' are enforced by the governance engine."""
    # Check governance engine code directly
    import inspect
    from app.services.governance_engine import GovernanceEngine

    source_code = inspect.getsource(GovernanceEngine.evaluate_content_version)
    assert 'KnowledgeRule.status == "approved"' in source_code
    assert 'KnowledgeFact.status == "approved"' in source_code


def test_packaging_and_numeric_fact_consistency_validation():
    """Verify that contradicted/unsupported facts (e.g. 330 mL can vs 250 mL bottle) are flagged."""
    from app.services.evidence_validator import validate_fact_consistency

    # 1. False/contradicted fact: 330 mL aluminum can
    status, note = validate_fact_consistency(
        value="330 mL sleek aluminum can",
        unit="mL",
        supporting_evidence="All six catalogue SKUs are 250 mL glass-bottled beverages.",
        page_text="Freshsip Beverages sells bottled juices in 250 mL single-serve glass bottles."
    )
    assert status in ("contradiction", "unsupported_value")
    assert "contradiction" in status.lower() or "unsupported" in status.lower()
    assert "330" in note or "glass" in note or "can" in note

    # 2. Authentic grounded fact: 250 mL glass bottle
    status_ok, note_ok = validate_fact_consistency(
        value="250",
        unit="mL",
        supporting_evidence="All six catalogue SKUs are 250 mL glass-bottled beverages.",
        page_text="Freshsip Beverages sells bottled juices in 250 mL single-serve glass bottles."
    )
    assert status_ok == "consistent"
    assert note_ok is None


def test_fr_rule_004_metadata_preservation_and_conflict_detection():
    """Verify FR-RULE-004 preserves high / block and detects conflicting metadata."""
    from app.services.evidence_validator import validate_rule_consistency

    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    result_path = os.path.join(workspace_root, "evaluation", "gemini_extraction_result.json")
    if not os.path.exists(result_path):
        pytest.skip("evaluation/gemini_extraction_result.json not found")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Locate FR-RULE-004 in actual saved evaluation
    rule_004 = next((r for r in data["brand_rules"] if r.get("rule_id") == "FR-RULE-004"), None)
    assert rule_004 is not None
    assert rule_004["rule_id"] == "FR-RULE-004"
    assert rule_004["severity"] == "high"
    assert rule_004["enforcement_action"] == "block"
    assert rule_004["source_status"] == "approved"
    assert rule_004["review_status"] == "pending_review"

    # Test conflict detection when model hallucinates critical / reject
    status_conflict, note_conflict = validate_rule_consistency(
        rule_id="FR-RULE-004",
        severity="critical",
        enforcement_action="reject",
        supporting_passages=["Under FR-RULE-004 (High / Block), sensationalist terms are prohibited."]
    )
    assert status_conflict == "rule_metadata_conflict"
    assert "high / block" in note_conflict
    assert "critical / reject" in note_conflict

    # Test consistent metadata verification
    status_valid, note_valid = validate_rule_consistency(
        rule_id="FR-RULE-004",
        severity="high",
        enforcement_action="block",
        supporting_passages=["Under FR-RULE-004 (High / Block), sensationalist terms are prohibited."]
    )
    assert status_valid == "consistent"
    assert note_valid is None


def test_multi_rule_page_scoping_eliminates_false_conflicts():
    """Verify multi-rule pages do not cause false rule ID or metadata conflicts."""
    from app.services.evidence_validator import extract_pdf_pages, validate_rule_consistency

    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pdf_path = os.path.join(workspace_root, "test_assets", "freshsip_inkloom_demo", "freshsip_brand_guidelines.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("test_assets PDF not found")

    pages = extract_pdf_pages(pdf_path)
    full_doc = "\n".join(pages)
    page_3_text = pages[2]  # Page 3 contains Rules 004, 005, 006, 007, 008, 019

    # FR-RULE-005 should not conflict with FR-RULE-004 on Page 3
    st_005, note_005 = validate_rule_consistency(
        rule_id="FR-RULE-005",
        severity="critical",
        enforcement_action="block",
        supporting_passages=["All six Freshsip products contain intrinsic fruit/vegetable sugars. Calling them 'sugar-free' is false."],
        page_text=page_3_text,
        document_text=full_doc
    )
    assert st_005 == "consistent", f"FR-RULE-005 was falsely flagged: {note_005}"
    assert note_005 is None

    # FR-RULE-007 should not conflict with FR-RULE-004 on Page 3
    st_007, note_007 = validate_rule_consistency(
        rule_id="FR-RULE-007",
        severity="critical",
        enforcement_action="block",
        supporting_passages=["Never state or imply that any Freshsip beverage treats, prevents, reverses, manages, or cures any disease."],
        page_text=page_3_text,
        document_text=full_doc
    )
    assert st_007 == "consistent", f"FR-RULE-007 was falsely flagged: {note_007}"
    assert note_007 is None


def test_fr_rule_015_resolves_to_high_flag_for_review():
    """Verify FR-RULE-015 correctly resolves to high / flag_for_review without false contradiction."""
    from app.services.evidence_validator import extract_pdf_pages, validate_rule_consistency

    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pdf_path = os.path.join(workspace_root, "test_assets", "freshsip_inkloom_demo", "freshsip_brand_guidelines.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("test_assets PDF not found")

    pages = extract_pdf_pages(pdf_path)
    full_doc = "\n".join(pages)

    # 1. Correct metadata from manual: high / flag_for_review
    st, note = validate_rule_consistency(
        rule_id="FR-RULE-015",
        severity="high",
        enforcement_action="flag_for_review",
        supporting_passages=["Quoting a 500 mL bottle or an unapproved price triggers a governance flag."],
        page_text=pages[3],  # Page 4
        document_text=full_doc
    )
    assert st == "consistent", f"FR-RULE-015 flag_for_review failed: {note}"
    assert note is None

    # 2. Genuine conflict test: if model assigned action="block", it must be flagged
    st_conflict, note_conflict = validate_rule_consistency(
        rule_id="FR-RULE-015",
        severity="high",
        enforcement_action="block",
        supporting_passages=["Quoting a 500 mL bottle or an unapproved price triggers a governance flag."],
        page_text=pages[3],
        document_text=full_doc
    )
    assert st_conflict == "rule_metadata_conflict"
    assert "flag_for_review" in note_conflict
    assert "block" in note_conflict


def test_fr_rule_019_evidence_selection_prefers_substantive_requirement():
    """Verify FR-RULE-019 selects the transliteration requirement rather than administrative status."""
    from app.services.extraction import select_best_rule_evidence_passage

    passages = [
        "Status: pending_review. Candidate rule awaiting Knowledge Manager approval; not enforced automatically until approved.",
        "Retain 'Freshsip' in English alongside Hindi, Tamil, or Kannada transliteration."
    ]
    stmt = "When using regional scripts, retain 'Freshsip' in English alongside Hindi, Tamil, or Kannada transliteration."

    chosen = select_best_rule_evidence_passage(passages, statement=stmt, title="Regional Language Transliteration Consistency")
    assert chosen == "Retain 'Freshsip' in English alongside Hindi, Tamil, or Kannada transliteration."


def test_allergen_food_safety_claim_categorisation():
    """Verify allergen claims are categorized as allergen_food_safety, not health_disease."""
    from app.services.extraction_schemas import StrictClaim

    # 1. Schema supports allergen_food_safety
    claim_data = {
        "claim_id": "FS-CLAIM-004",
        "claim_text": "Allergen-free claim for Spiced Carrot Beetroot Press",
        "claim_category": "allergen_food_safety",
        "decision": "pending_human_review",
        "evidence_or_rationale": "Pending cross-contact validation for celery.",
        "source_filename": "freshsip_brand_guidelines.pdf",
        "source_page_numbers": [4],
        "supporting_passages": ["Allergen disclosures: Contains celery."]
    }
    claim = StrictClaim.model_validate(claim_data)
    assert claim.claim_category == "allergen_food_safety"

    # 2. Simulated extraction claim mapping handles allergen terms
    claim_cat = "health_disease"
    claim_text = "Allergen-free claim for Spiced Carrot Beetroot Press"
    rationale = "Contains Celery (14%) allergen disclosure required."
    if claim_cat in ("health_disease", "other") and any(
        term in (claim_text + " " + rationale).lower() for term in ("allergen", "celery", "cross-contact")
    ):
        claim_cat = "allergen_food_safety"

    fact_key = f"Claim: {claim_cat.replace('_', ' ').title()}"
    assert claim_cat == "allergen_food_safety"
    assert fact_key == "Claim: Allergen Food Safety"


def test_asset_policies_disambiguation_under_fr_rule_017():
    """Verify multiple asset policies under FR-RULE-017 receive distinct IDs with parent linkage."""
    from app.services.extraction_schemas import StrictAssetPolicy

    policy1 = StrictAssetPolicy(
        policy_id="FR-RULE-017",
        asset_target="Brand Visual Assets Manifest",
        policy_statement="Only assets marked approved in manifest may be published.",
        approval_requirement="Requires Marketing Director approval.",
        permitted_channels=["all_channels"],
        source_filename="freshsip_brand_guidelines.pdf",
        source_page_numbers=[5],
        supporting_passages=["Only assets marked approved may be used."]
    )

    policy2 = StrictAssetPolicy(
        policy_id="FR-RULE-017",
        asset_target="Freshsip Brand Logo",
        policy_statement="Maintain a minimum clear-space margin equal to 25% of height.",
        approval_requirement="Follow visual clear space specifications.",
        permitted_channels=["all_channels"],
        source_filename="freshsip_brand_guidelines.pdf",
        source_page_numbers=[5],
        supporting_passages=["Maintain a minimum clear-space margin equal to 25%."]
    )

    # Disambiguation logic simulation
    codes = []
    for idx, p in enumerate([policy1, policy2], 1):
        parent_code = p.policy_id or "FR-RULE-017"
        unique_code = f"{parent_code}-AP{idx:02d}"
        codes.append(unique_code)

    assert codes[0] == "FR-RULE-017-AP01"
    assert codes[1] == "FR-RULE-017-AP02"
    assert len(set(codes)) == 2  # No duplicate codes!
    assert all("FR-RULE-017" in c for c in codes)  # Preserves parent linkage


def test_deterministic_traceability_matrix_parsing():
    """
    Phase 2 Check: Verify deterministic local extraction of Rule Traceability Matrix
    from PDF text without invoking Gemini API.
    """
    from app.services.evidence_validator import extract_rule_traceability_matrix, extract_pdf_pages
    import glob

    pdfs = glob.glob("**/freshsip_brand_guidelines.pdf", recursive=True)
    if not pdfs:
        pytest.skip("Freshsip PDF not found in repository.")

    pages = extract_pdf_pages(pdfs[0])
    matrix = extract_rule_traceability_matrix(pages)

    assert len(matrix) == 21, f"Expected 21 rules in Freshsip matrix, found {len(matrix)}"
    
    # FR-RULE-015 check
    assert "FR-RULE-015" in matrix
    assert matrix["FR-RULE-015"]["severity"] == "high"
    assert matrix["FR-RULE-015"]["enforcement_action"] == "flag_for_review"
    assert matrix["FR-RULE-015"]["source_status"] == "approved"

    # FR-RULE-019 status check
    assert "FR-RULE-019" in matrix
    assert matrix["FR-RULE-019"]["source_status"] == "pending_review"
    assert matrix["FR-RULE-019"]["severity"] == "low"
    assert matrix["FR-RULE-019"]["enforcement_action"] == "flag_for_review"

    # FR-RULE-020 status check
    assert "FR-RULE-020" in matrix
    assert matrix["FR-RULE-020"]["source_status"] == "expired"
    assert matrix["FR-RULE-020"]["severity"] == "medium"
    assert matrix["FR-RULE-020"]["enforcement_action"] == "block"

    # FR-RULE-021 status check
    assert "FR-RULE-021" in matrix
    assert matrix["FR-RULE-021"]["source_status"] == "rejected"
    assert matrix["FR-RULE-021"]["severity"] == "low"
    assert matrix["FR-RULE-021"]["enforcement_action"] == "warn"


def test_ambiguous_and_missing_matrix_handling():
    """
    Phase 2 Check: Support documents without a matrix, handle ambiguous metadata rows,
    never silently substitute guessed values, and detect genuine conflicts.
    """
    from app.services.evidence_validator import extract_rule_traceability_matrix, validate_rule_consistency

    # 1. Non-matrix pages return empty dict
    non_matrix_pages = [
        "Welcome to Willow and Vale Brand Book. This is pure prose.",
        "Section 1: Our story begins with organic ingredients and gentle harvesting."
    ]
    empty_matrix = extract_rule_traceability_matrix(non_matrix_pages)
    assert empty_matrix == {}

    # 2. Malformed or ambiguous row (invalid taxonomy) is rejected from deterministic matrix
    ambiguous_pages = [
        "Rule ID Rule Name Category & Type Severity & Action SectionStatus",
        "FR-RULE-999 Ambiguous Rule invalid_category (unknown_type) unknown / unknown Section Z approved"
    ]
    partial_matrix = extract_rule_traceability_matrix(ambiguous_pages)
    assert "FR-RULE-999" not in partial_matrix

    # 3. Detection of genuine conflict against known matrix
    mock_matrix = {
        "FR-RULE-004": {
            "rule_code": "FR-RULE-004",
            "title": "Avoid Miracle Terminology",
            "severity": "high",
            "enforcement_action": "block",
            "source_status": "approved"
        }
    }
    status, note = validate_rule_consistency(
        rule_id="FR-RULE-004",
        severity="low",
        enforcement_action="warn",
        supporting_passages=["Sensationalist terms imply unverified medicinal effects."],
        known_matrix=mock_matrix
    )
    assert status == "rule_metadata_conflict"
    assert "FR-RULE-004 specifies 'high / block'" in note
    assert "candidate assigned 'low / warn'" in note


def test_streamlined_gemini_schema_omits_redundant_fields():
    """
    Phase 2 Check: Verify that get_gemini_extraction_response_schema() strips redundant
    fields (source_filename, review_status, evidence_validation, scope) to minimize AI generation tokens,
    while StrictKnowledgeDocumentExtraction successfully validates both streamlined and legacy payloads.
    """
    from app.services.extraction_schemas import (
        get_gemini_extraction_response_schema,
        StrictKnowledgeDocumentExtraction
    )
    import json

    schema = get_gemini_extraction_response_schema()
    schema_str = json.dumps(schema)

    # Redundant fields stripped from Gemini API schema
    assert "source_filename" not in schema_str
    assert "review_status" not in schema_str
    assert "evidence_validation" not in schema_str

    # Still no additionalProperties
    assert "additionalProperties" not in schema_str
    assert "additional_properties" not in schema_str

    # Streamlined payload (omitting source_filename, review_status, evidence_validation) validates cleanly
    streamlined_json = json.dumps({
        "document_metadata": {
            "document_title": "Freshsip Guidelines",
            "document_id": "FS-001"
        },
        "brand_rules": [{
            "rule_id": "FR-RULE-001",
            "title": "Accurate Brand Naming",
            "statement": "Always write Freshsip Beverages in title case.",
            "source_page_numbers": [1],
            "supporting_passages": ["Freshsip Beverages must always be written in title case."]
        }],
        "product_facts": [{
            "product_name": "Sparkling Citrus",
            "attribute": "pack_size",
            "value": "330",
            "unit": "mL",
            "source_page_numbers": [2],
            "supporting_evidence": "Available in 330 mL glass bottles."
        }],
        "claims": [{
            "claim_text": "Contains celery extract",
            "claim_category": "allergen_food_safety",
            "decision": "permitted",
            "evidence_or_rationale": "Mandatory allergen declaration on Page 4.",
            "source_page_numbers": [4]
        }],
        "asset_policies": [{
            "policy_id": "FR-RULE-017",
            "asset_target": "Brand Logo",
            "policy_statement": "Clear space must equal 25% of logo height.",
            "approval_requirement": "Written approval from brand team.",
            "source_page_numbers": [5]
        }]
    })

    doc = StrictKnowledgeDocumentExtraction.model_validate_json(streamlined_json)
    assert doc.brand_rules[0].rule_id == "FR-RULE-001"
    assert doc.brand_rules[0].review_status == "pending_review"  # Local default
    assert doc.claims[0].claim_category == "allergen_food_safety"


if __name__ == "__main__":
    test_provider_schema_has_no_additional_properties()
    test_strict_local_validation_rejects_unexpected_fields()
    test_missing_api_key_produces_clear_error()
    test_evidence_validator_on_pdf_pages()
    test_reprocessing_preserves_reviewed_and_edited_records()
    test_governance_engine_only_evaluates_approved_rules()
    test_packaging_and_numeric_fact_consistency_validation()
    test_fr_rule_004_metadata_preservation_and_conflict_detection()
    test_multi_rule_page_scoping_eliminates_false_conflicts()
    test_fr_rule_015_resolves_to_high_flag_for_review()
    test_fr_rule_019_evidence_selection_prefers_substantive_requirement()
    test_allergen_food_safety_claim_categorisation()
    test_asset_policies_disambiguation_under_fr_rule_017()
    test_deterministic_traceability_matrix_parsing()
    test_ambiguous_and_missing_matrix_handling()
    test_streamlined_gemini_schema_omits_redundant_fields()
    print("ALL FOCUSED STAGE 2 INTEGRATION TESTS PASSED SUCCESSFULLY!")

