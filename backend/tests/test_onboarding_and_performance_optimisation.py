import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.database import engine, get_db, SessionLocal
from app.models.organization import User, OrganizationMembership, Organization
from app.models.brand import Brand
from app.models.content import ContentItem, ContentVersion
from app.models.knowledge import KnowledgeSource
from app.services.auth import create_access_token


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_tokens(db_session):
    # Ensure fresh admin/creator/reviewer
    creator = db_session.query(User).filter(User.email == "creator@freshsip.demo").first()
    reviewer = db_session.query(User).filter(User.email == "reviewer@freshsip.demo").first()
    admin = db_session.query(User).filter(User.email == "admin@freshsip.demo").first()

    creator_membership = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == creator.id
    ).first()

    org_id = creator_membership.organization_id
    creator_token = create_access_token({"sub": creator.id, "email": creator.email, "org_id": org_id})
    reviewer_token = create_access_token({"sub": reviewer.id, "email": reviewer.email, "org_id": org_id})
    admin_token = create_access_token({"sub": admin.id, "email": admin.email, "org_id": org_id})

    return {
        "creator_headers": {"Authorization": f"Bearer {creator_token}", "X-Organization-Id": org_id},
        "reviewer_headers": {"Authorization": f"Bearer {reviewer_token}", "X-Organization-Id": org_id},
        "admin_headers": {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id},
        "org_id": org_id,
        "creator_id": creator.id
    }


def test_retired_guideline_pdf_upload_rejected(client, auth_tokens):
    """
    Test 5: Retired organisation guideline PDF upload categories (pdf_brand_guidelines,
    pdf_product_knowledge) are rejected with clear HTTP 400 validation error.
    """
    headers = auth_tokens["reviewer_headers"]
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy content")

    # 1. Attempt pdf_brand_guidelines
    res1 = client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        data={"source_type": "pdf_brand_guidelines", "title": "Old Style Guide"},
        files={"file": ("guide.pdf", dummy_pdf, "application/pdf")}
    )
    assert res1.status_code == 400
    assert "retired" in res1.json()["detail"].lower()
    assert "brand profile form" in res1.json()["detail"].lower()

    # 2. Attempt pdf_product_knowledge
    dummy_pdf.seek(0)
    res2 = client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        data={"source_type": "pdf_product_knowledge", "title": "Old Product Specs"},
        files={"file": ("specs.pdf", dummy_pdf, "application/pdf")}
    )
    assert res2.status_code == 400
    assert "retired" in res2.json()["detail"].lower()


def test_supporting_doc_evidence_preserved(client, auth_tokens, db_session):
    """
    Test 6: Existing evidence-document PDF functionality is preserved.
    Supporting evidence documents (supporting_doc) can still be uploaded and viewed.
    """
    headers = auth_tokens["reviewer_headers"]
    dummy_pdf = io.BytesIO(b"%PDF-1.4 1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n165\n%%EOF")

    res = client.post(
        "/api/v1/knowledge/upload",
        headers=headers,
        data={"source_type": "supporting_doc", "title": "Regulatory Compliance Certificate"},
        files={"file": ("compliance_cert.pdf", dummy_pdf, "application/pdf")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["source_type"] == "supporting_doc"
    assert "compliance_cert.pdf" in data["filename"]
    assert "supporting evidence document" in data["extracted_summary"].lower()

    # Clean up test source
    source_id = data["id"]
    src = db_session.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if src:
        db_session.delete(src)
        db_session.commit()


def test_image_advertisement_upload_allowed(client, auth_tokens):
    """
    Test 7: Image advertisement creatives (PNG, JPG, WEBP) continue to be accepted.
    """
    headers = auth_tokens["creator_headers"]

    # Create dummy PNG in memory
    img = Image.new("RGB", (600, 600), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    res = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("promo_banner.png", buf, "image/png")}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_pdf"] is False
    assert body["format"] == "PNG"
    assert body["width"] == 600
    assert body["height"] == 600
    assert body["page_count"] == 1


def test_pdf_advertisement_upload_rejected(client, auth_tokens):
    """
    Test 8: New PDF advertisement uploads are rejected with HTTP 400.
    """
    headers = auth_tokens["creator_headers"]
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy ad")

    res = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("advertisement_deck.pdf", dummy_pdf, "application/pdf")}
    )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "no longer supported" in detail
    assert "png, jpg, or webp" in detail


def test_draft_listing_does_not_download_or_parse_pdf(client, auth_tokens, db_session):
    """
    Test 9: Draft listing requires zero remote file downloads and zero PDF parsing.
    _build_version_out() sets is_pdf=True and page_count=None for historical PDFs without disk I/O.
    """
    headers = auth_tokens["creator_headers"]
    org_id = auth_tokens["org_id"]
    creator_id = auth_tokens["creator_id"]

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()

    # Create historical draft in DB with a .pdf poster path
    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=creator_id,
        title="Historical PDF Pitch Deck",
        channel="Print Ad",
        current_version_num=1,
        status="draft"
    )
    db_session.add(item)
    db_session.flush()

    ver = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Historical marketing print ad copy",
        checksum="dummy_checksum_12345",
        created_by=creator_id,
        poster_file_path=f"{org_id}/posters/historical_deck.pdf"
    )
    db_session.add(ver)
    db_session.commit()

    # Mock storage_service and pdf_service to ensure neither is touched during draft listing
    with patch("app.services.storage.storage_service.get_file_path_for_processing") as mock_get_file, \
         patch("app.services.storage.storage_service.check_exists") as mock_check_exists:

        res = client.get("/api/v1/content", headers=headers)
        assert res.status_code == 200

        # Neither check_exists nor download should be invoked during listing
        assert mock_get_file.call_count == 0
        assert mock_check_exists.call_count == 0

        # Verify historical draft output representation
        items = res.json()
        target = next((i for i in items if i["id"] == item.id), None)
        assert target is not None
        assert target["latest_version"]["is_pdf"] is True
        assert target["latest_version"]["page_count"] is None  # Accurately nullable without hardcoding 1

    # Cleanup test item
    db_session.delete(ver)
    db_session.delete(item)
    db_session.commit()


def test_database_connection_pool_configuration():
    """
    Test 17: Database engine connection pool is configured with pool_size=5,
    max_overflow=5, pool_timeout=15, pool_recycle=300 for PostgreSQL instances.
    """
    if engine.name == "postgresql":
        pool = engine.pool
        assert pool.size() == 5
        assert pool._max_overflow == 5
        assert pool._timeout == 15
        assert pool._recycle == 300
        assert pool._pre_ping is True
    else:
        # SQLite engines in isolated test environments
        assert engine.name == "sqlite"

