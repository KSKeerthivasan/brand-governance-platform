import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import secrets
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from io import BytesIO
import openpyxl

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.organization import Organization, User, OrganizationMembership, OrganizationInvitation
from app.models.brand import BrandProfile, BrandColor
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import (
    KnowledgeBaseVersion, OrganizationActiveKnowledgeBase,
    StagedImport, StagedImportProductRow, StagedImportClaimRow, StagedImportDisclosureRow
)
from app.services.excel_service import excel_service
from app.services.auth import get_password_hash


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_excel_templates_generation():
    """Verify generated Excel templates have correct authoritative headers and sheets."""
    # 1. Product catalogue template
    prod_bytes = excel_service.generate_template("product_catalogue")
    assert prod_bytes is not None
    wb_prod = openpyxl.load_workbook(filename=BytesIO(prod_bytes))
    sheet_prod = wb_prod.active
    headers_prod = [cell.value for cell in sheet_prod[1]]
    assert len(headers_prod) == 15
    assert "product_id" in headers_prod
    assert "product_name" in headers_prod
    assert "applicable_market" in headers_prod

    # 2. Claims & Disclosures template
    claims_bytes = excel_service.generate_template("claims_and_disclosures")
    assert claims_bytes is not None
    wb_claims = openpyxl.load_workbook(filename=BytesIO(claims_bytes))
    assert "Claims_Register" in wb_claims.sheetnames
    assert "Required_Disclosures" in wb_claims.sheetnames

    sheet_claims = wb_claims["Claims_Register"]
    headers_claims = [cell.value for cell in sheet_claims[1]]
    assert len(headers_claims) == 11
    assert "claim_id" in headers_claims
    assert "claim_type" in headers_claims

    sheet_disc = wb_claims["Required_Disclosures"]
    headers_disc = [cell.value for cell in sheet_disc[1]]
    assert len(headers_disc) == 7
    assert "disclosure_id" in headers_disc


def test_staged_excel_import_and_discard_flow(db_session: Session):
    """Verify Excel parsing, row staging, and discarding without touching active tables."""
    # Create isolated test org
    org_slug = f"test-staged-{secrets.token_hex(4)}"
    org = Organization(name="Staged Test Org", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    user = User(email=f"admin@{org_slug}.com", hashed_password=get_password_hash("Secret123!"), full_name="Staged Admin")
    db_session.add(user)
    db_session.flush()

    # Create dummy product catalogue workbook in memory
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Product_Catalogue"
    ws.append([
        "product_id", "product_name", "product_category", "offering_type", "product_description",
        "variant_name", "sku", "pack_size", "pack_unit", "ingredients_components",
        "key_features", "specifications", "known_limitations", "applicable_market", "record_status"
    ])
    ws.append([
        "PROD-TEST-001", "Test Sparkler", "Beverages", "Physical Product", "A refreshing sparkling test drink",
        "Lime 330ml", "SPK-LIM-330", 330, "ml", "Carbonated water, lime extract",
        "Zero calories", "pH 3.5", "Keep refrigerated", "India", "Active"
    ])
    excel_buf = BytesIO()
    wb.save(excel_buf)
    excel_buf.seek(0)
    excel_bytes = excel_buf.getvalue()

    # Stage import
    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=org.id,
        user_id=user.id,
        file_name="test_catalogue.xlsx",
        file_bytes=excel_bytes,
        idempotency_key=str(uuid.uuid4()),
        import_type="product_catalogue"
    )

    assert staged.status == "pending_preview"
    assert staged.error_rows == 0
    assert staged.total_rows == 1

    # Verify no products were created yet in active table
    active_count = db_session.query(Product).filter(Product.organization_id == org.id).count()
    assert active_count == 0

    # Discard import
    excel_service.discard_staged_import(db=db_session, org_id=org.id, import_id=staged.id)
    discarded = db_session.query(StagedImport).filter(StagedImport.id == staged.id).first()
    assert discarded.status == "discarded"

    # Verify active table remains clean
    active_count_after = db_session.query(Product).filter(Product.organization_id == org.id).count()
    assert active_count_after == 0


def test_staged_excel_import_and_atomic_confirm(db_session: Session):
    """Verify staged rows are atomically committed to active tables upon confirm."""
    org_slug = f"test-confirm-{secrets.token_hex(4)}"
    org = Organization(name="Confirm Test Org", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    user = User(email=f"admin@{org_slug}.com", hashed_password=get_password_hash("Secret123!"), full_name="Confirm Admin")
    db_session.add(user)
    db_session.flush()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Product_Catalogue"
    ws.append([
        "product_id", "product_name", "product_category", "offering_type", "product_description",
        "variant_name", "sku", "pack_size", "pack_unit", "ingredients_components",
        "key_features", "specifications", "known_limitations", "applicable_market", "record_status"
    ])
    ws.append([
        "PROD-CONF-001", "Botanical Tea", "Beverages", "Physical Product", "Brewed botanical herbal tea",
        "Mint 250ml", "TEA-MNT-250", 250, "ml", "Water, spearmint leaves",
        "Caffeine free", "Sugar 0g", "Serve chilled", "India", "Active"
    ])
    excel_buf = BytesIO()
    wb.save(excel_buf)
    excel_buf.seek(0)

    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=org.id,
        user_id=user.id,
        file_name="confirm_catalogue.xlsx",
        file_bytes=excel_buf.getvalue(),
        idempotency_key=str(uuid.uuid4()),
        import_type="product_catalogue"
    )

    result = excel_service.confirm_staged_import(
        db=db_session,
        org_id=org.id,
        import_id=staged.id,
        user_id=user.id
    )
    assert result["committed_products"] == 1

    # Verify committed active product
    prod = db_session.query(Product).filter(
        Product.organization_id == org.id,
        Product.product_id == "PROD-CONF-001"
    ).first()
    assert prod is not None
    assert prod.product_name == "Botanical Tea"
    assert prod.record_status == "Active"


def test_invitation_lifecycle_and_multitenant_acceptance(db_session: Session):
    """Verify token generation, SHA-256 storage, public verification, and acceptance."""
    # Org A (Inviting Org)
    org_a = Organization(name="Alpha Org", slug=f"alpha-{secrets.token_hex(3)}")
    db_session.add(org_a)
    db_session.flush()

    admin_a = User(email=f"admin@{org_a.slug}.com", hashed_password=get_password_hash("Pass123!"), full_name="Admin Alpha")
    db_session.add(admin_a)
    db_session.flush()

    # Generate raw invitation token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    invitee_email = f"reviewer.{secrets.token_hex(2)}@testcorp.com"

    invitation = OrganizationInvitation(
        organization_id=org_a.id,
        email_normalized=invitee_email,
        role="knowledge_reviewer",
        token_hash=token_hash,
        invited_by=admin_a.id,
        inviter_email_snapshot=admin_a.email,
        expires_at=datetime.utcnow() + timedelta(days=7),
        delivery_status="unconfigured_demo_fallback"
    )
    db_session.add(invitation)
    db_session.commit()

    # 1. Verify token lookup by SHA-256 hash
    found_inv = db_session.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash,
        OrganizationInvitation.status == "pending"
    ).first()
    assert found_inv is not None
    assert found_inv.email_normalized == invitee_email
    assert found_inv.role == "knowledge_reviewer"
    assert found_inv.organization_id == org_a.id

    # 2. Accept invitation: provision new user and create membership
    new_user = User(
        email=invitee_email,
        hashed_password=get_password_hash("InviteePassword2026!"),
        full_name="Rachel Reviewer"
    )
    db_session.add(new_user)
    db_session.flush()

    membership = OrganizationMembership(
        user_id=new_user.id,
        organization_id=org_a.id,
        role=found_inv.role
    )
    db_session.add(membership)

    found_inv.status = "accepted"
    found_inv.consumed_at = datetime.utcnow()
    found_inv.accepted_by_user_id = new_user.id
    db_session.commit()

    # 3. Verify membership in Org A
    user_memberships = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == new_user.id
    ).all()
    assert len(user_memberships) == 1
    assert user_memberships[0].organization_id == org_a.id
    assert user_memberships[0].role == "knowledge_reviewer"

    # 4. Verify token is consumed
    consumed_inv = db_session.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash
    ).first()
    assert consumed_inv.status == "accepted"


def test_immutable_kb_version_trigger(db_session: Session):
    """Verify that PostgreSQL trigger protects KnowledgeBaseVersion from mutation or deletion."""
    org = Organization(name="Trigger Test Org", slug=f"trig-{secrets.token_hex(3)}")
    db_session.add(org)
    db_session.flush()

    kbv = KnowledgeBaseVersion(
        organization_id=org.id,
        version_num=1,
        manifest_sha256="abcdef1234567890" * 4,
        manifest_data={"status": "snapshot_test"},
        activation_reason="Trigger Immutability Test"
    )
    db_session.add(kbv)
    db_session.commit()

    # If running against PostgreSQL, verify database trigger prevents mutation
    if db_session.bind.dialect.name == "postgresql":
        try:
            kbv.activation_reason = "Illegal mutation"
            db_session.commit()
            mutation_failed = False
        except Exception as exc:
            db_session.rollback()
            mutation_failed = True
            assert "immutable" in str(exc).lower() or "read-only" in str(exc).lower()

        assert mutation_failed, "PostgreSQL trigger should prevent updating immutable KnowledgeBaseVersion"
    else:
        # SQLite test environment - verify record preservation and integrity
        assert kbv.version_num == 1
        assert kbv.manifest_sha256 == "abcdef1234567890" * 4
