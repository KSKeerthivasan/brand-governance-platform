import pytest
import io
import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import get_db, SessionLocal
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand, BrandProfile, BrandColor
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import (
    KnowledgeBaseVersion, OrganizationActiveKnowledgeBase,
    StagedImport
)
from app.services.auth import create_access_token, get_password_hash
from app.services.excel_service import excel_service

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="module")
def test_setup(db_session):
    # Setup test organization and reviewer
    org_slug = "test-onboarding-co"
    existing_org = db_session.query(Organization).filter(Organization.slug == org_slug).first()
    if existing_org:
        # Clean up existing test org data
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": existing_org.id})
        db_session.commit()

    org = Organization(name="Test Onboarding Co", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    user = User(
        email="reviewer@testonboarding.demo",
        hashed_password=get_password_hash("SecretPassword123!"),
        full_name="Knowledge Reviewer Test",
        is_active=True
    )
    db_session.add(user)
    db_session.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=OrganizationRole.KNOWLEDGE_REVIEWER
    )
    db_session.add(membership)

    brand = Brand(organization_id=org.id, name="Test Brand", description="Onboarding test brand")
    db_session.add(brand)
    db_session.commit()

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": OrganizationRole.KNOWLEDGE_REVIEWER,
        "is_demo": False
    })

    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "org": org,
        "user": user,
        "headers": headers
    }

    # Cleanup
    try:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
        db_session.commit()
    except Exception:
        pass


def test_download_excel_templates(test_setup):
    headers = test_setup["headers"]

    # 1. Product catalogue template
    r1 = client.get("/api/v1/knowledge/templates/product_catalogue", headers=headers)
    assert r1.status_code == 200
    assert "spreadsheetml.sheet" in r1.headers["content-type"]
    wb1 = openpyxl.load_workbook(io.BytesIO(r1.content))
    assert "Product_Catalogue" in wb1.sheetnames

    # 2. Claims and disclosures template
    r2 = client.get("/api/v1/knowledge/templates/claims_and_disclosures", headers=headers)
    assert r2.status_code == 200
    wb2 = openpyxl.load_workbook(io.BytesIO(r2.content))
    assert "Claims_Register" in wb2.sheetnames
    assert "Required_Disclosures" in wb2.sheetnames

    # 3. Invalid template
    r3 = client.get("/api/v1/knowledge/templates/invalid_type", headers=headers)
    assert r3.status_code == 400


def test_brand_profile_crud(test_setup):
    headers = test_setup["headers"]

    profile_data = {
        "brand_name": "Test Brand Co",
        "brand_description": "Artisanal beverage company committed to organic integrity.",
        "approved_taglines": ["Pure botanicals. Pure life."],
        "brand_personality": ["Calm", "Sophisticated", "Honest"],
        "preferred_tone": ["Serene", "Refined", "Direct"],
        "tones_to_avoid": ["Hype", "Aggressive"],
        "preferred_terminology": ["Cold-extracted", "Wild-harvested"],
        "prohibited_terminology": ["Miracle cure", "Guaranteed fat burner"],
        "writing_style": "Elevated and minimal",
        "approved_languages": ["English"],
        "primary_heading_font": "Cormorant Garamond",
        "secondary_body_font": "Inter",
        "additional_approved_fonts": ["Newsreader"],
        "typography_instructions": "Maintain at least 1.5x scale hierarchy between headings and body text.",
        "visual_style": ["Clean", "Minimalist", "Earthy"],
        "preferred_imagery_style": ["Botanical close-ups", "Soft daylight"],
        "preferred_backgrounds": ["Muted parchment", "Soft linen"],
        "visual_styles_to_avoid": ["High contrast neons"],
        "logo_usage_instructions": "Never rotate or apply gradient overlays to the primary logo.",
        "colors": [
            {
                "colour_name": "Sage Green",
                "colour_family": "Green",
                "colour_role": "Primary",
                "hex_value": "#6B8E23",
                "rgb_r": 107,
                "rgb_g": 142,
                "rgb_b": 35
            },
            {
                "colour_name": "Warm Cream",
                "colour_family": "Neutral",
                "colour_role": "Background",
                "hex_value": "#FFFDD0",
                "rgb_r": 255,
                "rgb_g": 253,
                "rgb_b": 208
            }
        ]
    }

    # 1. Save profile
    r = client.post("/api/v1/knowledge/brand-profile", json=profile_data, headers=headers)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["brand_name"] == "Test Brand Co"
    assert len(saved["colors"]) == 2
    assert saved["primary_heading_font"] == "Cormorant Garamond"

    # 2. Get profile
    r_get = client.get("/api/v1/knowledge/brand-profile", headers=headers)
    assert r_get.status_code == 200
    fetched = r_get.json()
    assert fetched["brand_name"] == "Test Brand Co"
    assert len(fetched["colors"]) == 2
    assert fetched["colors"][0]["colour_name"] == "Sage Green"


def test_staged_product_import_flow(test_setup, db_session):
    headers = test_setup["headers"]
    org_id = test_setup["org"].id

    # 1. Generate product catalogue Excel
    raw_template = excel_service.generate_template("product_catalogue")

    # 2. Upload and Preview
    files = {"file": ("test_products.xlsx", raw_template, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r_prev = client.post(
        "/api/v1/knowledge/import/product_catalogue/preview",
        files=files,
        data={"idempotency_key": "test-key-p01"},
        headers=headers
    )
    assert r_prev.status_code == 200, r_prev.text
    preview = r_prev.json()
    assert preview["import_type"] == "product_catalogue"
    assert preview["total_rows"] == 3
    assert preview["error_rows"] == 0
    assert preview["valid_rows"] == 3
    assert len(preview["rows"]) == 3
    import_id = preview["id"]

    # 3. Verify zero mutation to active products before confirm
    active_prods_before = db_session.query(Product).filter(Product.organization_id == org_id).count()
    assert active_prods_before == 0

    # 4. Fetch preview via GET
    r_get_prev = client.get(f"/api/v1/knowledge/import/{import_id}/preview", headers=headers)
    assert r_get_prev.status_code == 200
    assert r_get_prev.json()["id"] == import_id

    # 5. Confirm staged import
    r_confirm = client.post(f"/api/v1/knowledge/import/{import_id}/confirm", headers=headers)
    assert r_confirm.status_code == 200, r_confirm.text
    confirm_data = r_confirm.json()
    assert confirm_data["status"] == "success"
    assert confirm_data["committed_products"] == 3

    # 6. Verify products now exist in active table
    active_prods_after = db_session.query(Product).filter(Product.organization_id == org_id).all()
    assert len(active_prods_after) == 3
    prod_ids = {p.product_id for p in active_prods_after}
    assert "FS-P001" in prod_ids
    assert "FS-P003" in prod_ids


def test_staged_claims_and_disclosures_flow(test_setup, db_session):
    headers = test_setup["headers"]
    org_id = test_setup["org"].id

    # 1. Generate claims and disclosures template (references FS-P001 which is now in catalogue)
    raw_template = excel_service.generate_template("claims_and_disclosures")

    # 2. Upload and Preview
    files = {"file": ("test_claims.xlsx", raw_template, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r_prev = client.post(
        "/api/v1/knowledge/import/claims_and_disclosures/preview",
        files=files,
        data={"idempotency_key": "test-key-c01"},
        headers=headers
    )
    assert r_prev.status_code == 200, r_prev.text
    preview = r_prev.json()
    assert preview["import_type"] == "claims_and_disclosures"
    assert preview["has_disclosures"] is True
    assert preview["error_rows"] == 0
    assert preview["total_rows"] == 5  # 3 claims + 2 disclosures
    import_id = preview["id"]

    # 3. Confirm import atomically
    r_confirm = client.post(f"/api/v1/knowledge/import/{import_id}/confirm", headers=headers)
    assert r_confirm.status_code == 200, r_confirm.text
    confirm_data = r_confirm.json()
    assert confirm_data["status"] == "success"
    assert confirm_data["committed_claims"] == 3
    assert confirm_data["committed_disclosures"] == 2

    # 4. Verify in DB
    claims = db_session.query(Claim).filter(Claim.organization_id == org_id).all()
    assert len(claims) == 3
    disclosures = db_session.query(RequiredDisclosure).filter(RequiredDisclosure.organization_id == org_id).all()
    assert len(disclosures) == 2


def test_activate_knowledge_base_manifest(test_setup, db_session):
    headers = test_setup["headers"]
    org_id = test_setup["org"].id

    # Activate
    r_act = client.post(
        "/api/v1/knowledge/activate",
        json={"activation_reason": "End-to-end onboarding activation test"},
        headers=headers
    )
    assert r_act.status_code == 200, r_act.text
    act_data = r_act.json()
    assert act_data["version_num"] == 1
    assert len(act_data["manifest_sha256"]) == 64
    assert act_data["counts"]["products"] == 3
    assert act_data["counts"]["claims"] == 3
    assert act_data["counts"]["required_disclosures"] == 2
    version_id = act_data["version_id"]

    # Verify active pointer
    active_ptr = db_session.query(OrganizationActiveKnowledgeBase).filter(
        OrganizationActiveKnowledgeBase.organization_id == org_id
    ).first()
    assert active_ptr is not None
    assert active_ptr.active_version_id == version_id

    # Verify database trigger immutability protection (active on PostgreSQL)
    if db_session.bind.dialect.name == "postgresql":
        db_session.commit()
        with pytest.raises(Exception) as exc_info:
            db_session.execute(
                text("UPDATE knowledge_base_versions SET activation_reason = 'hacked' WHERE id = :id"),
                {"id": version_id}
            )
            db_session.commit()
        db_session.rollback()
        assert "immutable" in str(exc_info.value).lower() or "knowledge_base_versions" in str(exc_info.value).lower()
