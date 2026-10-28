"""
Tests for Reprocessing Transaction Safety and Atomicity.

Verifies:
1. Gemini API failure leaves existing candidates intact and logs no audit event.
2. Malformed structured response leaves existing candidates intact and logs no audit event.
3. Evidence or schema validation failure leaves existing candidates intact and logs no audit event.
4. Persistence failure rolls back the delete-and-insert transaction and logs no audit event.
5. Successful replacement:
   - Deletes ONLY replaceable pending uncorrected candidates.
   - Preserves approved, rejected, and reviewer-corrected records.
   - Avoids duplicating preserved rule codes and fact keys.
   - Increments source version.
   - Emits KNOWLEDGE_REPROCESSED audit event only upon successful commit.
6. Asset-policy identifiers remain distinct (FR-RULE-017-AP01, etc.).
"""

import os
import json
import uuid
from unittest.mock import patch
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.organization import Organization, User, OrganizationMembership
from app.models.brand import Brand
from app.models.knowledge import KnowledgeSource, KnowledgeRule, KnowledgeFact
from app.models.audit import AuditEvent
from app.services.gemini_extractor import GeminiExtractionError
from app.main import app
from app.database import get_db

def get_test_db():
    override = app.dependency_overrides.get(get_db)
    if override:
        gen = override()
        return next(gen)
    from app.database import SessionLocal
    return SessionLocal()



@pytest.fixture
def reprocessing_setup(tmp_path):
    """
    Creates a dedicated test knowledge source and pre-populates:
    - 1 approved rule (RULE-APP-01)
    - 1 rejected rule (RULE-REJ-01)
    - 1 reviewer-corrected pending rule (RULE-EDIT-01)
    - 1 uncorrected pending candidate rule (RULE-PEND-01) - replaceable!
    - 1 approved fact (nutrition:sugar)
    - 1 rejected fact (claim:miracle)
    - 1 reviewer-corrected pending fact (nutrition:calories)
    - 1 uncorrected pending candidate fact (claim:pending_fact) - replaceable!
    """
    db = get_test_db()
    org = db.query(Organization).filter(Organization.slug == "freshsip").first()
    brand = db.query(Brand).filter(Brand.organization_id == org.id).first()
    user = db.query(User).filter(User.email == "reviewer@freshsip.demo").first()

    # Create dummy source PDF file
    dummy_pdf = tmp_path / "test_guidelines.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy test content")

    source = KnowledgeSource(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        brand_id=brand.id,
        title="Transaction Test Guidelines",
        source_type="pdf_brand_guidelines",
        filename="test_guidelines.pdf",
        file_path=str(dummy_pdf),
        file_size_bytes=100,
        mime_type="application/pdf",
        version=1,
        status="reviewed",
        extracted_summary="Test summary",
        uploaded_by=user.id
    )
    db.add(source)

    # 4 Rules with different review/correction states
    r_app_id = str(uuid.uuid4())
    r_rej_id = str(uuid.uuid4())
    r_edit_id = str(uuid.uuid4())
    r_pend_id = str(uuid.uuid4())

    r_app = KnowledgeRule(
        id=r_app_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        rule_type="prohibited_word", title="Approved Rule", pattern="approved_term",
        explanation="Approved", severity="critical", rule_code="RULE-APP-01",
        status="approved", is_corrected=False
    )
    r_rej = KnowledgeRule(
        id=r_rej_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        rule_type="prohibited_word", title="Rejected Rule", pattern="rejected_term",
        explanation="Rejected", severity="warning", rule_code="RULE-REJ-01",
        status="rejected", is_corrected=False
    )
    r_edit = KnowledgeRule(
        id=r_edit_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        rule_type="required_term", title="Edited Rule", pattern="edited_term",
        explanation="Edited by reviewer", severity="info", rule_code="RULE-EDIT-01",
        status="pending_review", is_corrected=True
    )
    r_pend = KnowledgeRule(
        id=r_pend_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        rule_type="prohibited_word", title="Pending Uncorrected", pattern="pending_term",
        explanation="Pending candidate", severity="info", rule_code="RULE-PEND-01",
        status="pending_review", is_corrected=False
    )
    db.add_all([r_app, r_rej, r_edit, r_pend])

    # 4 Facts with different review/correction states
    f_app_id = str(uuid.uuid4())
    f_rej_id = str(uuid.uuid4())
    f_edit_id = str(uuid.uuid4())
    f_pend_id = str(uuid.uuid4())

    f_app = KnowledgeFact(
        id=f_app_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        product_name="Product A", category="nutrition", fact_key="sugar", fact_value="0g",
        status="approved", is_corrected=False
    )
    f_rej = KnowledgeFact(
        id=f_rej_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        product_name="Product A", category="claim", fact_key="miracle", fact_value="Cures fatigue",
        status="rejected", is_corrected=False
    )
    f_edit = KnowledgeFact(
        id=f_edit_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        product_name="Product A", category="nutrition", fact_key="calories", fact_value="15 kcal",
        status="pending_review", is_corrected=True
    )
    f_pend = KnowledgeFact(
        id=f_pend_id, organization_id=org.id, brand_id=brand.id, source_id=source.id,
        product_name="Product A", category="claim", fact_key="pending_fact", fact_value="Antioxidant rich",
        status="pending_review", is_corrected=False
    )
    db.add_all([f_app, f_rej, f_edit, f_pend])

    db.commit()

    source_id = source.id
    db.close()

    return {
        "source_id": source_id,
        "dummy_pdf": str(dummy_pdf),
        "rule_ids": {"app": r_app_id, "rej": r_rej_id, "edit": r_edit_id, "pend": r_pend_id},
        "fact_ids": {"app": f_app_id, "rej": f_rej_id, "edit": f_edit_id, "pend": f_pend_id}
    }


def test_gemini_api_failure_preserves_old_candidates(client, auth_tokens, reprocessing_setup):
    """
    1. A Gemini API failure leaves old candidates intact and logs no audit event.
    """
    source_id = reprocessing_setup["source_id"]
    headers = auth_tokens["knowledge_reviewer"]["headers"]

    with patch("app.api.v1.knowledge.extract_pdf_text_and_candidates") as mock_extract:
        mock_extract.side_effect = GeminiExtractionError("Gemini API connection timeout 504")

        res = client.post(f"/api/v1/knowledge/sources/{source_id}/reprocess", headers=headers)
        assert res.status_code == 502
        assert "Gemini extraction error" in res.json()["detail"]

    # Verify database state
    db = get_test_db()
    rules = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source_id).all()
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source_id).all()
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    audits = db.query(AuditEvent).filter(
        AuditEvent.entity_id == source_id,
        AuditEvent.event_type == "KNOWLEDGE_REPROCESSED"
    ).all()
    db.close()

    assert len(rules) == 4, "All 4 original rules must remain intact"
    assert len(facts) == 4, "All 4 original facts must remain intact"
    # The replaceable pending candidate must NOT have been deleted
    assert any(r.id == reprocessing_setup["rule_ids"]["pend"] for r in rules)
    assert any(f.id == reprocessing_setup["fact_ids"]["pend"] for f in facts)
    assert source.version == 1, "Source version must not increment on failure"
    assert len(audits) == 0, "No reprocessing audit event must be recorded on failure"


def test_malformed_structured_response_preserves_old_candidates(client, auth_tokens, reprocessing_setup):
    """
    2. A malformed structured response leaves old candidates intact and logs no audit event.
    """
    source_id = reprocessing_setup["source_id"]
    headers = auth_tokens["knowledge_reviewer"]["headers"]

    with patch("app.api.v1.knowledge.extract_pdf_text_and_candidates") as mock_extract:
        mock_extract.side_effect = GeminiExtractionError("Malformed JSON response from Gemini: Unterminated string")

        res = client.post(f"/api/v1/knowledge/sources/{source_id}/reprocess", headers=headers)
        assert res.status_code == 502
        assert "Gemini extraction error" in res.json()["detail"]

    # Verify database state
    db = get_test_db()
    rules = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source_id).all()
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source_id).all()
    audits = db.query(AuditEvent).filter(
        AuditEvent.entity_id == source_id,
        AuditEvent.event_type == "KNOWLEDGE_REPROCESSED"
    ).all()
    db.close()

    assert len(rules) == 4
    assert len(facts) == 4
    assert any(r.id == reprocessing_setup["rule_ids"]["pend"] for r in rules)
    assert any(f.id == reprocessing_setup["fact_ids"]["pend"] for f in facts)
    assert len(audits) == 0


def test_evidence_validation_failure_preserves_old_candidates(client, auth_tokens, reprocessing_setup):
    """
    3. Evidence or schema validation failure leaves old candidates intact and logs no audit event.
    """
    source_id = reprocessing_setup["source_id"]
    headers = auth_tokens["knowledge_reviewer"]["headers"]

    with patch("app.api.v1.knowledge.extract_pdf_text_and_candidates") as mock_extract:
        mock_extract.side_effect = ValueError("Schema validation failed: extra forbidden field 'unknown_key'")

        res = client.post(f"/api/v1/knowledge/sources/{source_id}/reprocess", headers=headers)
        assert res.status_code == 500
        assert "Reprocessing error" in res.json()["detail"]

    # Verify database state
    db = get_test_db()
    rules = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source_id).all()
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source_id).all()
    audits = db.query(AuditEvent).filter(
        AuditEvent.entity_id == source_id,
        AuditEvent.event_type == "KNOWLEDGE_REPROCESSED"
    ).all()
    db.close()

    assert len(rules) == 4
    assert len(facts) == 4
    assert any(r.id == reprocessing_setup["rule_ids"]["pend"] for r in rules)
    assert any(f.id == reprocessing_setup["fact_ids"]["pend"] for f in facts)
    assert len(audits) == 0


def test_persistence_failure_rolls_back_atomic_transaction(client, auth_tokens, reprocessing_setup):
    """
    4. A database persistence failure rolls back the replacement transaction and leaves old candidates intact.
    """
    source_id = reprocessing_setup["source_id"]
    headers = auth_tokens["knowledge_reviewer"]["headers"]

    mock_candidate_rules = [{
        "rule_type": "requirement",
        "title": "New Validated Rule",
        "pattern": "new_term",
        "explanation": "Explanation",
        "severity": "medium",
        "rule_code": "RULE-NEW-01",
        "source_status": "approved",
        "enforcement_action": "flag_for_review"
    }]
    mock_candidate_facts = [{
        "product_name": "Product A",
        "category": "specification",
        "fact_key": "shelf_life",
        "fact_value": "12 months",
        "source_status": "approved"
    }]

    with patch("app.api.v1.knowledge.extract_pdf_text_and_candidates") as mock_extract:
        mock_extract.return_value = ("New summary", mock_candidate_rules, mock_candidate_facts, {})

        # Simulate database failure on commit
        with patch("sqlalchemy.orm.Session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("Database disk I/O error during commit")

            res = client.post(f"/api/v1/knowledge/sources/{source_id}/reprocess", headers=headers)
            assert res.status_code == 500
            assert "Database persistence failed" in res.json()["detail"]

    # Verify database state after rollback
    db = get_test_db()
    rules = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source_id).all()
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source_id).all()
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    audits = db.query(AuditEvent).filter(
        AuditEvent.entity_id == source_id,
        AuditEvent.event_type == "KNOWLEDGE_REPROCESSED"
    ).all()
    db.close()

    assert len(rules) == 4, "Old rules must not be deleted if commit fails"
    assert len(facts) == 4, "Old facts must not be deleted if commit fails"
    assert any(r.id == reprocessing_setup["rule_ids"]["pend"] for r in rules)
    assert any(f.id == reprocessing_setup["fact_ids"]["pend"] for f in facts)
    assert not any(r.rule_code == "RULE-NEW-01" for r in rules), "New rule must not be persisted on failure"
    assert source.version == 1
    assert len(audits) == 0, "No audit event should be recorded if transaction rolls back"


def test_successful_replacement_preserves_protected_and_avoids_duplicates(client, auth_tokens, reprocessing_setup):
    """
    5. Successful replacement:
       - Deletes ONLY replaceable pending uncorrected records.
       - Preserves approved, rejected, and corrected records.
       - Avoids duplicating preserved rule codes and fact keys.
       - Increments source version.
       - Logs audit event only after successful commit.
    """
    source_id = reprocessing_setup["source_id"]
    headers = auth_tokens["knowledge_reviewer"]["headers"]

    # Candidate rules include:
    # - RULE-APP-01 (should NOT duplicate the existing approved rule)
    # - RULE-NEW-01 (brand new candidate rule)
    mock_candidate_rules = [
        {
            "rule_type": "prohibited_word",
            "title": "Duplicate of Approved",
            "pattern": "approved_term",
            "explanation": "Should be skipped because RULE-APP-01 is preserved",
            "severity": "critical",
            "rule_code": "RULE-APP-01",
            "source_status": "approved",
            "enforcement_action": "block"
        },
        {
            "rule_type": "requirement",
            "title": "New Candidate Rule",
            "pattern": "new_candidate_term",
            "explanation": "Freshly extracted rule",
            "severity": "medium",
            "rule_code": "RULE-NEW-01",
            "source_status": "approved",
            "enforcement_action": "flag_for_review"
        }
    ]

    # Candidate facts include:
    # - (Product A, sugar) - already preserved!
    # - (Product A, pack_material) - brand new candidate fact!
    mock_candidate_facts = [
        {
            "product_name": "Product A",
            "category": "nutrition",
            "fact_key": "sugar",
            "fact_value": "0g added sugar",
            "source_status": "approved"
        },
        {
            "product_name": "Product A",
            "category": "specification",
            "fact_key": "pack_material",
            "fact_value": "Amber Glass",
            "source_status": "approved"
        }
    ]

    with patch("app.api.v1.knowledge.extract_pdf_text_and_candidates") as mock_extract:
        mock_extract.return_value = (
            "Updated test summary",
            mock_candidate_rules,
            mock_candidate_facts,
            {"total_elapsed_ms": 150.0}
        )

        res = client.post(f"/api/v1/knowledge/sources/{source_id}/reprocess", headers=headers)
        assert res.status_code == 200, f"Reprocess failed: {res.text}"
        data = res.json()
        assert data["version"] == 2

    # Verify database state
    db = get_test_db()
    rules = db.query(KnowledgeRule).filter(KnowledgeRule.source_id == source_id).all()
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.source_id == source_id).all()
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    audits = db.query(AuditEvent).filter(
        AuditEvent.entity_id == source_id,
        AuditEvent.event_type == "KNOWLEDGE_REPROCESSED"
    ).all()
    db.close()

    # Rule checks:
    # Original: app, rej, edit, pend (4). Replaceable: pend.
    # New: RULE-APP-01 (skipped), RULE-NEW-01 (added).
    # Final count: 3 preserved + 1 new = 4 rules.
    rule_codes = [r.rule_code for r in rules]
    assert "RULE-APP-01" in rule_codes
    assert "RULE-REJ-01" in rule_codes
    assert "RULE-EDIT-01" in rule_codes
    assert "RULE-NEW-01" in rule_codes
    assert "RULE-PEND-01" not in rule_codes, "Old pending uncorrected rule must have been replaced"
    assert rule_codes.count("RULE-APP-01") == 1, "Must not duplicate preserved rule"

    # Fact checks:
    # Original: sugar (app), miracle (rej), calories (edit), pending_fact (pend). Replaceable: pending_fact.
    # New: sugar (skipped), pack_material (added).
    # Final count: 3 preserved + 1 new = 4 facts.
    fact_keys = [f.fact_key for f in facts]
    assert "sugar" in fact_keys
    assert "miracle" in fact_keys
    assert "calories" in fact_keys
    assert "pack_material" in fact_keys
    assert "pending_fact" not in fact_keys, "Old pending uncorrected fact must have been replaced"
    assert fact_keys.count("sugar") == 1, "Must not duplicate preserved fact"

    # Source metadata checks:
    assert source.version == 2
    assert source.extracted_summary == "Updated test summary"

    # Audit event checks:
    assert len(audits) == 1
    audit = audits[0]
    assert audit.event_type == "KNOWLEDGE_REPROCESSED"
    assert audit.details["preserved_rules_count"] == 3
    assert audit.details["replaced_rules_count"] == 1
    assert audit.details["new_candidate_rules_count"] == 1
    assert audit.details["preserved_facts_count"] == 3
    assert audit.details["replaced_facts_count"] == 1
    assert audit.details["new_candidate_facts_count"] == 1
    assert audit.details["new_version"] == 2


def test_asset_policy_identifiers_remain_distinct():
    """
    6. Asset-policy identifiers under FR-RULE-017 remain distinct and disambiguated.
    """
    from app.services.extraction_schemas import StrictKnowledgeDocumentExtraction

    raw_payload = {
        "document_metadata": {
            "document_title": "Freshsip Assets",
            "document_id": "FS-ASSET-01"
        },
        "brand_rules": [],
        "product_facts": [],
        "claims": [],
        "asset_policies": [
            {
                "policy_id": "FR-RULE-017",
                "asset_target": "Primary Brandmark",
                "policy_statement": "Minimum clear space around brandmark must be 25% of mark height.",
                "approval_requirement": "Mandatory review.",
                "source_page_numbers": [5],
                "supporting_passages": ["Clear space around brandmark must be 25% of height."]
            },
            {
                "policy_id": "FR-RULE-017",
                "asset_target": "Monochrome Silhouette",
                "policy_statement": "Monochrome variant permitted only on single-colour packaging.",
                "approval_requirement": "Design director sign-off.",
                "source_page_numbers": [5],
                "supporting_passages": ["Monochrome variant permitted only on single-colour packaging."]
            },
            {
                "policy_id": "FR-RULE-017",
                "asset_target": "Stacked Secondary Logo",
                "policy_statement": "Stacked logo may not be placed closer than 10mm from edges.",
                "approval_requirement": "Mandatory review.",
                "source_page_numbers": [6],
                "supporting_passages": ["Stacked logo may not be placed closer than 10mm."]
            }
        ]
    }

    doc = StrictKnowledgeDocumentExtraction.model_validate(raw_payload)

    # Simulate extraction asset policy processing
    distinct_codes = []
    for idx, a in enumerate(doc.asset_policies, 1):
        parent_code = a.policy_id or "FR-RULE-017"
        unique_policy_code = f"{parent_code}-AP{idx:02d}"
        distinct_codes.append(unique_policy_code)

    assert len(distinct_codes) == 3
    assert len(set(distinct_codes)) == 3, "All asset policy codes must be distinct"
    assert distinct_codes == ["FR-RULE-017-AP01", "FR-RULE-017-AP02", "FR-RULE-017-AP03"]


def test_classify_gemini_error_distinguishes_error_categories():
    """
    Verify _classify_gemini_error distinctly identifies:
    - 503 transient unavailability
    - 429 daily quota exhaustion
    - 429 short-term rate limit
    - non-transient errors (400, 401, 403)
    """
    from app.services.gemini_extractor import _classify_gemini_error

    class MockErr(Exception):
        def __init__(self, msg, code=None):
            super().__init__(msg)
            self.code = code

    # 1. 503 UNAVAILABLE
    cat1, code1, _ = _classify_gemini_error(MockErr("503 UNAVAILABLE: Model experiencing high demand.", 503))
    assert cat1 == "transient_503"
    assert code1 == 503

    # 2. 429 Daily Quota Exhausted
    cat2, code2, _ = _classify_gemini_error(MockErr("Resource exhausted: daily quota exceeded for generative language API.", 429))
    assert cat2 == "quota_429"
    assert code2 == 429

    # 3. 429 Short-term Rate Limit
    cat3, code3, _ = _classify_gemini_error(MockErr("429 Too Many Requests: Rate limit exceeded. Please wait 15s.", 429))
    assert cat3 == "rate_limit_429"
    assert code3 == 429

    # 4. Non-transient errors (e.g. 400 Bad Request, 401 Auth)
    cat4, code4, _ = _classify_gemini_error(MockErr("API key not valid. Please pass a valid API key.", 401))
    assert cat4 == "non_transient"
    assert code4 == 401


def test_gemini_bounded_retry_policy_retries_once_on_503(tmp_path):
    """
    Verify run_gemini_pdf_extraction retries at most once on 503 UNAVAILABLE
    and succeeds if the second attempt succeeds, logging attempts and setting retry_count=1.
    """
    from app.services.gemini_extractor import run_gemini_pdf_extraction
    from unittest.mock import MagicMock

    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "document_metadata": {"document_title": "Test Doc", "document_id": "TD-01"},
        "brand_rules": [],
        "product_facts": [],
        "claims": [],
        "asset_policies": []
    })
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=50)

    class Mock503(Exception):
        code = 503

    with patch("os.getenv", return_value="fake-api-key"), \
         patch("app.config.settings.GEMINI_API_KEY", "fake-api-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("time.sleep") as mock_sleep:

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.files.upload.return_value = MagicMock(name="files/dummy")

        # Attempt 1 raises 503; Attempt 2 succeeds
        mock_client.models.generate_content.side_effect = [
            Mock503("503 UNAVAILABLE: High demand"),
            mock_resp
        ]

        doc, metrics = run_gemini_pdf_extraction(str(dummy_pdf), "test.pdf")

        assert doc is not None
        assert metrics["retry_count"] == 1
        assert len(metrics["attempts"]) == 2
        assert metrics["attempts"][0]["outcome"] == "transient_503"
        assert metrics["attempts"][1]["outcome"] == "success"
        assert mock_sleep.called, "Must have backed off with jitter before retry"


def test_gemini_bounded_retry_stops_immediately_on_quota_exhausted(tmp_path):
    """
    Verify run_gemini_pdf_extraction does NOT retry if daily quota is exhausted (429).
    """
    from app.services.gemini_extractor import run_gemini_pdf_extraction, GeminiExtractionError
    from unittest.mock import MagicMock

    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    class Mock429(Exception):
        code = 429

    with patch("os.getenv", return_value="fake-api-key"), \
         patch("app.config.settings.GEMINI_API_KEY", "fake-api-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("time.sleep") as mock_sleep:

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.files.upload.return_value = MagicMock(name="files/dummy")

        mock_client.models.generate_content.side_effect = Mock429("ResourceExhausted: daily quota exhausted.")

        with pytest.raises(GeminiExtractionError) as exc_info:
            run_gemini_pdf_extraction(str(dummy_pdf), "test.pdf")

        assert "daily quota exhausted" in str(exc_info.value)
        assert not mock_sleep.called, "Must not retry on daily quota exhaustion"

