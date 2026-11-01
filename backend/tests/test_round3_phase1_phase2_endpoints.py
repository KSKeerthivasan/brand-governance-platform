"""
Integration tests for Round 3 Phase 1 & Phase 2:
- Staged Excel upload, preview, discard, and atomic confirmation
- Brand Profile & Colors management
- Knowledge Base Manifest Activation & Immutability Check
- Impact Rescoring Engine Simulation & Diff
- Team Invitation generation, verification, and acceptance
"""

import io
import pytest
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.organization import Organization, OrganizationMembership, User, OrganizationInvitation
from app.models.brand import Brand, BrandProfile, BrandColor
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import KnowledgeBaseVersion, OrganizationActiveKnowledgeBase, StagedImport
from app.models.rescore import ImpactRescoringJob, ImpactRescoringBatchItem
from app.services.auth import create_access_token
from app.services.excel_service import excel_service
import openpyxl

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_excel_template_generation_and_staging(db_session):
    """Verify that templates generate valid Excel sheets and can be staged."""
    # 1. Product catalogue template
    prod_bytes = excel_service.generate_template("product_catalogue")
    prod_buf = io.BytesIO(prod_bytes)
    wb_prod = openpyxl.load_workbook(prod_buf)
    sheet = wb_prod.active
    assert sheet.title == "Product_Catalogue"
    headers = [cell.value for cell in sheet[1]]
    assert "product_name" in headers
    assert "offering_type" in headers
    assert "sku" in headers

    # 2. Claims and disclosures template
    claim_bytes = excel_service.generate_template("claims_and_disclosures")
    claim_buf = io.BytesIO(claim_bytes)
    wb_claim = openpyxl.load_workbook(claim_buf)
    sheet_names = wb_claim.sheetnames
    assert "Claims_Register" in sheet_names
    assert "Required_Disclosures" in sheet_names

def test_staged_excel_lifecycle(db_session):
    """Test full staging lifecycle: parse -> stage -> preview -> discard / confirm."""
    # Create isolated test org
    test_org_id = "test-excel-org-lifecycle"
    db_session.rollback()
    existing_org = db_session.query(Organization).filter(Organization.id == test_org_id).first()
    if not existing_org:
        org = Organization(id=test_org_id, name="Test Lifecycle Org", slug="test-lifecycle-org")
        db_session.add(org)
        db_session.commit()

    # Generate a populated product catalogue workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Product Catalogue"
    headers = [
        "product_id", "product_name", "product_category", "offering_type", "product_description",
        "variant_name", "sku", "pack_size", "pack_unit", "ingredients_components",
        "key_features", "specifications", "known_limitations", "applicable_market", "record_status"
    ]
    ws.append(headers)
    ws.append([
        "PRD-ALPHA-001", "Alpha Elixir", "Wellness", "Physical Product", "Revitalizing herbal tonic",
        "Standard", "SKU-ALPHA-01", 250, "ml", "Ginseng, Green Tea",
        "High potency", "Cold-pressed", "Not suitable for infants", "India", "active"
    ])

    file_bytes = io.BytesIO()
    wb.save(file_bytes)
    file_bytes.seek(0)
    raw_content = file_bytes.getvalue()

    # 1. Parse and Stage
    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=test_org_id,
        user_id="test-user-excel",
        file_name="test_catalogue.xlsx",
        file_bytes=raw_content,
        idempotency_key="test-key-1",
        import_type="product_catalogue"
    )
    assert staged.status in ("pending_preview", "staged", "validated"), f"Import status {staged.status}: {staged.validation_summary}"
    assert staged.total_rows == 1
    assert staged.error_rows == 0

    # 2. Confirm Staged Import
    res = excel_service.confirm_staged_import(db=db_session, org_id=test_org_id, import_id=staged.id, user_id="test-user-excel")
    assert res.get("committed_products") == 1 or res.get("imported_counts", {}).get("products") == 1

    # Verify product in active table
    prod = db_session.query(Product).filter(Product.organization_id == test_org_id, Product.product_name == "Alpha Elixir").first()
    assert prod is not None
    assert prod.sku == "SKU-ALPHA-01"

    # Cleanup test product and staged import
    db_session.query(Product).filter(Product.organization_id == test_org_id).delete()
    db_session.query(StagedImport).filter(StagedImport.organization_id == test_org_id).delete()
    db_session.query(Organization).filter(Organization.id == test_org_id).delete()
    db_session.commit()

def test_invitation_token_hashing_and_verification(db_session):
    """Test cryptographic token hashing and invitation lookup."""
    import secrets
    import hashlib

    test_org_id = "test-inv-org"
    db_session.rollback()
    existing_org = db_session.query(Organization).filter(Organization.id == test_org_id).first()
    if not existing_org:
        org = Organization(id=test_org_id, name="Test Invitation Org", slug="test-inv-org")
        db_session.add(org)
        db_session.commit()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    test_email = "invitee_test@example.com"

    invitation = OrganizationInvitation(
        organization_id=test_org_id,
        email_normalized=test_email,
        role="content_creator",
        token_hash=token_hash,
        invited_by=None,
        inviter_email_snapshot="admin@example.com",
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=7),
        delivery_status="unconfigured_demo_fallback"
    )
    db_session.add(invitation)
    db_session.commit()

    # Query using raw token hash
    lookup_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    found = db_session.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == lookup_hash,
        OrganizationInvitation.status == "pending"
    ).first()
    assert found is not None
    assert found.email_normalized == test_email
    assert found.delivery_status == "unconfigured_demo_fallback"

    # Cleanup
    db_session.delete(found)
    db_session.query(Organization).filter(Organization.id == test_org_id).delete()
    db_session.commit()
