import os
import io
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import app
from app.database import SessionLocal
from app.models.organization import Organization, OrganizationMembership, User
from app.models.brand import Brand
from app.models.knowledge import KnowledgeSource, KnowledgeRule, KnowledgeFact
from app.services.gemini_extractor import GeminiExtractionError
from app.services.extraction import extract_pdf_text_and_candidates, extract_local_pdf_candidates
from app.services.auth import create_access_token


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers(db_session):
    # Use existing Freshsip admin / reviewer
    user = db_session.query(User).filter(User.email == "reviewer@freshsip.demo").first()
    if not user:
        user = db_session.query(User).first()
    membership = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id
    ).first()
    token = create_access_token({"sub": user.id, "email": user.email, "org_id": membership.organization_id})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": membership.organization_id
    }, membership.organization_id, user.id


def test_scenario_gemini_succeeds_normal_workflow(tmp_path):
    """
    Scenario 1: Gemini succeeds. The normal document extraction operates as before.
    """
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    dummy_pdf_pages = ["Page 1: Freshsip Governance. FR-RULE-001 Organic Only requirement critical block approved Section A"]
    mock_doc = MagicMock()
    mock_doc.brand_rules = []
    mock_doc.asset_policies = []
    mock_doc.product_facts = []
    mock_doc.claims = []
    mock_doc.document_metadata = MagicMock(
        document_title="Mock Guidelines",
        document_id="MOCK-01",
        version="1.0",
        non_governance_elements=[]
    )

    with patch("app.services.extraction.extract_pdf_pages", return_value=dummy_pdf_pages), \
         patch("app.services.extraction.run_gemini_pdf_extraction", return_value=(mock_doc, {"upload_duration_ms": 10.0, "generation_duration_ms": 50.0})):
        
        summary, rules, facts, timings = extract_pdf_text_and_candidates(str(dummy_pdf), "dummy.pdf")
        assert "Mock Guidelines" in summary
        assert timings["outcome"] == "success"


def test_scenario_gemini_503_recovers_via_local_extraction(tmp_path):
    """
    Scenario 2: Gemini returns 503 UNAVAILABLE. The application recovers through local extraction.
    """
    dummy_pdf = tmp_path / "nexoratech.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    pdf_pages = [
        "Rule ID: NX-RULE-001\nRule title: Unsupported product claims\nCategory: Claims | Severity: High\nRequirement: Claims must be verified.\nExample of non-compliant content: '100% cure all'\nExample of compliant content: 'Helpful tonic'",
        "Rule ID: NX-RULE-002\nRule title: Security guarantees\nCategory: Security | Severity: High\nRequirement: Do not claim 100% secure.\nExample of non-compliant content: '100% secure workspace'"
    ]

    with patch("app.services.extraction.extract_pdf_pages", return_value=pdf_pages), \
         patch("app.services.extraction.run_gemini_pdf_extraction", side_effect=GeminiExtractionError("Gemini 503 UNAVAILABLE persists after 2 attempts")):

        summary, rules, facts, timings = extract_pdf_text_and_candidates(str(dummy_pdf), "nexoratech_guidelines.pdf")

        assert "[Local PDF Text Extraction — Gemini Unavailable]" in summary
        assert len(rules) == 2
        assert rules[0]["rule_code"] == "NX-RULE-001"
        assert rules[0]["severity"] == "high"
        assert rules[0]["status"] == "pending_review"  # Must NEVER be auto-approved
        assert "LOCAL_EXTRACTION" in rules[0]["uncertainty_notes"]
        assert rules[1]["rule_code"] == "NX-RULE-002"
        assert timings["extraction_mode"] == "local_fallback"
        assert timings["outcome"] == "recovered_locally"


def test_scenario_scanned_pdf_reports_limitation_honestly(tmp_path):
    """
    Scenario 3: The PDF contains no extractable text. The application reports the limitation honestly
    and offers the supported alternative (manual entry).
    """
    dummy_pdf = tmp_path / "scanned.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    empty_pdf_pages = ["", "   \n\n  ", ""]

    with patch("app.services.extraction.extract_pdf_pages", return_value=empty_pdf_pages), \
         patch("app.services.extraction.run_gemini_pdf_extraction", side_effect=GeminiExtractionError("Gemini 503 UNAVAILABLE")):

        summary, rules, facts, timings = extract_pdf_text_and_candidates(str(dummy_pdf), "scanned_handbook.pdf")

        assert "No extractable text could be recovered" in summary
        assert "scanned image" in summary
        assert len(rules) == 0
        assert len(facts) == 0
        assert timings["extraction_mode"] == "local_fallback_no_text"
        assert timings["outcome"] == "limitation_reported"


def test_scenario_retry_upload_avoids_duplicate_sources_and_rules(auth_headers, db_session):
    """
    Scenario 4: The same document is retried. No duplicate source or rule records are created.
    """
    headers, org_id, user_id = auth_headers
    client = TestClient(app)

    pdf_bytes = b"%PDF-1.4 sample content with Rule ID: TEST-RULE-001\nRule title: Test Rule\nRequirement: Test req\n"
    
    # 1. First upload
    with patch("app.services.extraction.run_gemini_pdf_extraction", side_effect=GeminiExtractionError("Gemini 503 UNAVAILABLE")):
        res1 = client.post(
            "/api/v1/knowledge/upload",
            headers=headers,
            data={"source_type": "pdf_brand_guidelines", "title": "Test Retry Doc"},
            files={"file": ("test_retry_doc.pdf", pdf_bytes, "application/pdf")}
        )
        assert res1.status_code == 200, res1.text
        data1 = res1.json()
        source_id1 = data1["id"]

    # Count sources with this filename
    cnt1 = db_session.query(KnowledgeSource).filter(
        KnowledgeSource.organization_id == org_id,
        KnowledgeSource.filename == "test_retry_doc.pdf"
    ).count()
    assert cnt1 == 1

    # 2. Second upload (retry with the exact same document)
    with patch("app.services.extraction.run_gemini_pdf_extraction", side_effect=GeminiExtractionError("Gemini 503 UNAVAILABLE")):
        res2 = client.post(
            "/api/v1/knowledge/upload",
            headers=headers,
            data={"source_type": "pdf_brand_guidelines", "title": "Test Retry Doc"},
            files={"file": ("test_retry_doc.pdf", pdf_bytes, "application/pdf")}
        )
        assert res2.status_code == 200, res2.text
        data2 = res2.json()
        source_id2 = data2["id"]

    # Verify ID is reused and no duplicate was created
    assert source_id1 == source_id2, "Must reuse existing KnowledgeSource record on retry"
    cnt2 = db_session.query(KnowledgeSource).filter(
        KnowledgeSource.organization_id == org_id,
        KnowledgeSource.filename == "test_retry_doc.pdf"
    ).count()
    assert cnt2 == 1, "Must not create duplicate KnowledgeSource records"

    # Cleanup test source
    src = db_session.query(KnowledgeSource).filter(KnowledgeSource.id == source_id1).first()
    if src:
        db_session.delete(src)
        db_session.commit()


def test_scenario_tenant_isolation_on_document_text(auth_headers, db_session):
    """
    Scenario 5: An organization cannot access another organization's documents or extracted content.
    """
    headers, org_id, user_id = auth_headers
    client = TestClient(app)

    # Find or create a source in a DIFFERENT organization
    other_org = db_session.query(Organization).filter(Organization.id != org_id).first()
    if not other_org:
        import uuid
        other_org = Organization(id=str(uuid.uuid4()), name="Other Org", slug="other-org")
        db_session.add(other_org)
        db_session.commit()

    other_source = db_session.query(KnowledgeSource).filter(
        KnowledgeSource.organization_id == other_org.id
    ).first()

    if not other_source:
        # Create a dummy source under the other organization
        other_source = KnowledgeSource(
            organization_id=other_org.id,
            title="Confidential Other Org Doc",
            source_type="pdf_brand_guidelines",
            filename="confidential_other.pdf",
            file_path="other/path.pdf",
            file_size_bytes=100,
            mime_type="application/pdf",
            status="pending_review"
        )
        db_session.add(other_source)
        db_session.commit()

    # Request the other org's source text using current org's credentials
    res = client.get(f"/api/v1/knowledge/sources/{other_source.id}/text", headers=headers)
    assert res.status_code == 404, "Must reject cross-tenant access to document text with 404 Not Found"
