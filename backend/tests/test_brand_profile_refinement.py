import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import SessionLocal
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand, BrandProfile, BrandColor
from app.services.auth import create_access_token, get_password_hash

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
    org_slug = "test-brand-profile-co"
    existing_org = db_session.query(Organization).filter(Organization.slug == org_slug).first()
    if existing_org:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": existing_org.id})
        db_session.commit()

    org = Organization(name="Test Brand Profile Co", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    user = User(
        email="reviewer@testbrandprofile.demo",
        hashed_password=get_password_hash("SecretPassword123!"),
        full_name="Reviewer User",
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

    brand = Brand(organization_id=org.id, name="Test Brand", description="Brand profile test brand")
    db_session.add(brand)
    db_session.commit()

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": OrganizationRole.KNOWLEDGE_REVIEWER,
        "is_demo": False
    })
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org.id
    }

    yield {
        "org": org,
        "user": user,
        "headers": headers,
        "client": client
    }

    # Cleanup
    try:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db_session.commit()
    except Exception:
        pass


def test_brand_profile_full_lifecycle(test_setup, db_session):
    client = test_setup["client"]
    headers = test_setup["headers"]
    org_id = test_setup["org"].id

    payload = {
        # Section A
        "brand_name": "Zenith Botanicals Co.",
        "brand_description": "Holistic cold-pressed plant adaptogens and organic hydration.",
        "approved_taglines": ["Rooted in Clarity", "Naturally Elevated"],
        "brand_personality": ["Pioneering", "Calm", "Transparent", "Grounded"],

        # Section B
        "writing_style": "Poetic yet scientifically precise, uplifting, empathetic, and grounded.",
        "spelling_convention": "British English",
        "writing_style_instructions": "Spell colour and flavour with u. Never use hype-words.",
        "approved_languages": ["en", "fr"],
        "preferred_tone": ["Mindful", "Authoritative", "Serene"],
        "tones_to_avoid": ["Aggressive", "Snarky", "Sensationalist"],
        "preferred_terminology": ["Whole-plant extraction", "Wild-harvested"],
        "prohibited_terminology": ["Miracle tonic", "Detox potion"],

        # Section C - Multi-color with repeated roles & custom usage
        "colors": [
            {
                "colour_name": "Zenith Emerald",
                "colour_family": "Green",
                "colour_role": "Primary",
                "hex_value": "#047857",
                "rgb_r": 4,
                "rgb_g": 120,
                "rgb_b": 87,
                "usage_instructions": "Primary brand mark and main headline typography"
            },
            {
                "colour_name": "Forest Sage",
                "colour_family": "Green",
                "colour_role": "Primary",  # Repeated role!
                "hex_value": "#065F46",
                "rgb_r": 6,
                "rgb_g": 95,
                "rgb_b": 70,
                "usage_instructions": "Alternative dark primary for light containers"
            },
            {
                "colour_name": "Morning Mist",
                "colour_family": "Neutral",
                "colour_role": "Background",
                "hex_value": "#F0FDF4",
                "rgb_r": 240,
                "rgb_g": 253,
                "rgb_b": 244,
                "usage_instructions": "Poster background base canvas"
            }
        ],

        # Section D
        "primary_heading_font": "Playfair Display",
        "secondary_body_font": "Inter",
        "typography_instructions": "Maintain 1.618x Golden Ratio heading to body scale ratio.",

        # Section E
        "preferred_imagery_style": ["Macro botanical photography", "Soft natural sunlight"],
        "preferred_backgrounds": ["Subtle organic parchment texture", "Clean airy daylight"],
        "preferred_visual_treatments": ["Feathered soft shadows", "16px rounded corners"],
        "visual_styles_to_avoid": ["Harsh neon flares", "Artificial plastic glares"],
        "logo_usage_instructions": "Clear zone must equal 100% of mark width. Never tint white logo."
    }

    # 1. Save Brand Profile
    r_save = client.post("/api/v1/knowledge/brand-profile", json=payload, headers=headers)
    assert r_save.status_code == 200, r_save.text
    saved = r_save.json()

    assert saved["brand_name"] == "Zenith Botanicals Co."
    assert saved["spelling_convention"] == "British English"
    assert saved["writing_style_instructions"] == "Spell colour and flavour with u. Never use hype-words."
    assert saved["brand_personality"] == ["Pioneering", "Calm", "Transparent", "Grounded"]
    assert saved["primary_heading_font"] == "Playfair Display"
    assert saved["secondary_body_font"] == "Inter"
    assert len(saved["colors"]) == 3
    assert saved["colors"][0]["colour_role"] == "Primary"
    assert saved["colors"][1]["colour_role"] == "Primary"  # repeated role preserved
    assert saved["colors"][0]["usage_instructions"] == "Primary brand mark and main headline typography"
    assert saved["preferred_visual_treatments"] == ["Feathered soft shadows", "16px rounded corners"]

    # 2. Get Brand Profile and verify reload
    r_get = client.get("/api/v1/knowledge/brand-profile", headers=headers)
    assert r_get.status_code == 200, r_get.text
    reloaded = r_get.json()

    assert reloaded["brand_name"] == "Zenith Botanicals Co."
    assert reloaded["spelling_convention"] == "British English"
    assert reloaded["brand_personality"] == ["Pioneering", "Calm", "Transparent", "Grounded"]
    assert len(reloaded["colors"]) == 3
    assert reloaded["colors"][1]["colour_name"] == "Forest Sage"

    # 3. Verify Optional Fields can remain empty/default
    sparse_payload = {
        "brand_name": "Minimalist Brand",
        "writing_style": "Understated and simple."
    }
    r_sparse = client.post("/api/v1/knowledge/brand-profile", json=sparse_payload, headers=headers)
    assert r_sparse.status_code == 200, r_sparse.text
    sparse_saved = r_sparse.json()
    assert sparse_saved["brand_name"] == "Minimalist Brand"
    assert sparse_saved["writing_style"] == "Understated and simple."
    assert sparse_saved["brand_personality"] == []
    assert sparse_saved["approved_taglines"] == []
    assert sparse_saved["spelling_convention"] is None
    assert sparse_saved["writing_style_instructions"] is None
    assert sparse_saved["primary_heading_font"] == "Inter"
    assert sparse_saved["secondary_body_font"] == "Roboto"
    assert sparse_saved["colors"] == []

    # 4. Mandatory field validation
    r_invalid = client.post("/api/v1/knowledge/brand-profile", json={"writing_style": "Missing name"}, headers=headers)
    assert r_invalid.status_code == 422  # validation error: brand_name is required
