import pytest
import json
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import SessionLocal
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand, BrandProfile, BrandColor
from app.models.knowledge import KnowledgeBaseVersion
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
def audit_setup(db_session):
    org_slug = "test-brand-audit-org"
    existing_org = db_session.query(Organization).filter(Organization.slug == org_slug).first()
    if existing_org:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": existing_org.id})
        db_session.commit()

    org = Organization(name="Audit Test Corp", slug=org_slug)
    db_session.add(org)
    db_session.flush()

    user = User(
        email="lead_reviewer@audittest.demo",
        hashed_password=get_password_hash("SecretAuditPass123!"),
        full_name="Lead Reviewer",
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

    brand = Brand(organization_id=org.id, name="Audit Brand", description="Audit testing")
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

    try:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db_session.commit()
    except Exception:
        pass


def test_language_empty_and_removal(audit_setup, db_session):
    """Test 2: Verify users can save empty languages and English is not implicitly forced."""
    headers = audit_setup["headers"]

    # 1. Save with completely empty approved_languages
    payload = {
        "brand_name": "Multilingual Global Co",
        "writing_style": "Global neutral",
        "approved_languages": []
    }
    r = client.post("/api/v1/knowledge/brand-profile", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["approved_languages"] == []

    # Reload from DB
    r_get = client.get("/api/v1/knowledge/brand-profile", headers=headers)
    assert r_get.status_code == 200
    assert r_get.json()["approved_languages"] == []

    # 2. Save with German and Japanese (no English)
    payload["approved_languages"] = ["de", "ja"]
    r2 = client.post("/api/v1/knowledge/brand-profile", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["approved_languages"] == ["de", "ja"]

    # 3. Remove German, leaving only Japanese
    payload["approved_languages"] = ["ja"]
    r3 = client.post("/api/v1/knowledge/brand-profile", json=payload, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["approved_languages"] == ["ja"]


def test_immutable_kb_version_manifest_integrity(audit_setup, db_session):
    """Test 4: Verify immutable KB activation, version incrementation, and SHA-256 differentiation."""
    headers = audit_setup["headers"]
    org_id = audit_setup["org"].id

    # Baseline Brand Profile
    profile_v1 = {
        "brand_name": "Quantum Labs",
        "brand_description": "Next-gen computing solutions",
        "brand_personality": ["Rigorous", "Pioneering"],
        "writing_style": "Crisp and analytical",
        "spelling_convention": "American English",
        "primary_heading_font": "Outfit",
        "secondary_body_font": "Inter",
        "colors": [
            {
                "colour_name": "Quantum Blue",
                "colour_family": "Blue",
                "colour_role": "Primary",
                "hex_value": "#1D4ED8",
                "rgb_r": 29,
                "rgb_g": 78,
                "rgb_b": 216,
                "usage_instructions": "Main headline typography"
            }
        ]
    }
    r_p1 = client.post("/api/v1/knowledge/brand-profile", json=profile_v1, headers=headers)
    assert r_p1.status_code == 200

    # 1. Activate v1
    r_act1 = client.post("/api/v1/knowledge/activate", json={"activation_reason": "V1 baseline"}, headers=headers)
    assert r_act1.status_code == 200, r_act1.text
    v1_data = r_act1.json()
    v1_version_num = v1_data["version_num"]
    v1_hash = v1_data["manifest_sha256"]

    kb_v1 = db_session.query(KnowledgeBaseVersion).filter(KnowledgeBaseVersion.id == v1_data["version_id"]).first()
    assert kb_v1 is not None
    manifest_v1_copy = json.loads(json.dumps(kb_v1.manifest_data))

    # 2. Change Brand Personality and Activate v2
    profile_v2 = dict(profile_v1)
    profile_v2["brand_personality"] = ["Rigorous", "Pioneering", "Visionary"]
    r_p2 = client.post("/api/v1/knowledge/brand-profile", json=profile_v2, headers=headers)
    assert r_p2.status_code == 200

    r_act2 = client.post("/api/v1/knowledge/activate", json={"activation_reason": "V2 personality update"}, headers=headers)
    assert r_act2.status_code == 200
    v2_data = r_act2.json()
    assert v2_data["version_num"] == v1_version_num + 1
    v2_hash = v2_data["manifest_sha256"]
    assert v2_hash != v1_hash, "Hash MUST differ when brand personality changes!"

    # Verify v1 historical record was not mutated
    db_session.refresh(kb_v1)
    assert kb_v1.manifest_data == manifest_v1_copy
    assert kb_v1.manifest_data["brand_profile"]["personality"] == ["Rigorous", "Pioneering"]

    # 3. Change Color usage_instructions and Activate v3
    profile_v3 = dict(profile_v2)
    profile_v3["colors"] = [
        {
            "colour_name": "Quantum Blue",
            "colour_family": "Blue",
            "colour_role": "Primary",
            "hex_value": "#1D4ED8",
            "rgb_r": 29,
            "rgb_g": 78,
            "rgb_b": 216,
            "usage_instructions": "Updated: Restrict strictly to logo elements only"
        }
    ]
    r_p3 = client.post("/api/v1/knowledge/brand-profile", json=profile_v3, headers=headers)
    assert r_p3.status_code == 200

    r_act3 = client.post("/api/v1/knowledge/activate", json={"activation_reason": "V3 color usage update"}, headers=headers)
    assert r_act3.status_code == 200
    v3_data = r_act3.json()
    assert v3_data["version_num"] == v2_data["version_num"] + 1
    v3_hash = v3_data["manifest_sha256"]
    assert v3_hash != v2_hash, "Hash MUST differ when color usage_instructions change!"

    # 4. Change Typography and Activate v4
    profile_v4 = dict(profile_v3)
    profile_v4["primary_heading_font"] = "Playfair Display"
    profile_v4["typography_instructions"] = "Scale ratio 2.0x required"
    r_p4 = client.post("/api/v1/knowledge/brand-profile", json=profile_v4, headers=headers)
    assert r_p4.status_code == 200

    r_act4 = client.post("/api/v1/knowledge/activate", json={"activation_reason": "V4 typography update"}, headers=headers)
    assert r_act4.status_code == 200
    v4_data = r_act4.json()
    assert v4_data["version_num"] == v3_data["version_num"] + 1
    v4_hash = v4_data["manifest_sha256"]
    assert v4_hash != v3_hash, "Hash MUST differ when typography settings change!"
