import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand

client = TestClient(app)

def test_onboard_organization_success():
    """
    Test successful organization onboarding with brand, admin, and membership creation.
    """
    payload = {
        "organization_name": "Veritas Tea Co.",
        "organization_slug": "veritas-tea",
        "brand_name": "Veritas Botanical Tea",
        "brand_description": "Pure organic cold-brewed botanicals and herbal infusions",
        "admin_full_name": "Victor Veritas",
        "admin_email": "admin@veritastea.com",
        "admin_password": "SecurePassword2026!"
    }
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 201, f"Onboarding failed: {res.text}"
    data = res.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "org_admin"
    assert data["organization_name"] == "Veritas Tea Co."
    assert data["organization_slug"] == "veritas-tea"
    assert data["user"]["email"] == "admin@veritastea.com"
    assert data["user"]["full_name"] == "Victor Veritas"

    # Verify authenticated access to /organizations/current
    headers = {
        "Authorization": f"Bearer {data['access_token']}",
        "X-Organization-Id": data["organization_id"]
    }
    org_res = client.get("/api/v1/organizations/current", headers=headers)
    assert org_res.status_code == 200
    assert org_res.json()["name"] == "Veritas Tea Co."

    # Verify brand was created
    brands_res = client.get("/api/v1/brands", headers=headers)
    assert brands_res.status_code == 200
    brands = brands_res.json()
    assert len(brands) == 1
    assert brands[0]["name"] == "Veritas Botanical Tea"

    # Verify membership list has Victor Veritas as org_admin
    members_res = client.get("/api/v1/organizations/members", headers=headers)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 1
    assert members[0]["user_email"] == "admin@veritastea.com"
    assert members[0]["role"] == "org_admin"

def test_onboard_duplicate_slug_rejected():
    """
    Test that duplicate organization slug returns 409 Conflict.
    """
    # Freshsip slug already exists from seed
    payload = {
        "organization_name": "Duplicate Freshsip",
        "organization_slug": "freshsip",
        "brand_name": "Duplicate Brand",
        "admin_full_name": "Dave Duplicate",
        "admin_email": "dave@duplicate.demo",
        "admin_password": "SecurePassword2026!"
    }
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()

def test_onboard_duplicate_admin_email_rejected():
    """
    Test that duplicate admin email returns 409 Conflict.
    """
    # admin@freshsip.demo already exists
    payload = {
        "organization_name": "Unique Org Name",
        "organization_slug": "unique-org-slug-xyz",
        "brand_name": "Unique Brand",
        "admin_full_name": "Alice Administrator",
        "admin_email": "admin@freshsip.demo",
        "admin_password": "SecurePassword2026!"
    }
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()

def test_onboard_invalid_slug_format():
    """
    Test slug validation rejects uppercase and invalid characters.
    """
    payload = {
        "organization_name": "Invalid Slug Org",
        "organization_slug": "Invalid_Slug!@#",
        "brand_name": "Brand Name",
        "admin_full_name": "Admin Name",
        "admin_email": "admin@invalidslug.com",
        "admin_password": "SecurePassword2026!"
    }
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 422

def test_onboard_short_password_rejected():
    """
    Test that passwords under 8 characters are rejected with 422.
    """
    payload = {
        "organization_name": "Short Password Org",
        "organization_slug": "short-pass-org",
        "brand_name": "Brand Name",
        "admin_full_name": "Admin Name",
        "admin_email": "admin@shortpass.com",
        "admin_password": "short"
    }
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 422

def test_new_organization_isolated_from_freshsip():
    """
    Verify complete tenant isolation: New organization admin cannot view or access Freshsip data.
    """
    # Onboard isolated tenant
    payload = {
        "organization_name": "Isolated Tenant Co.",
        "organization_slug": "isolated-tenant",
        "brand_name": "Isolated Brand",
        "admin_full_name": "Iso Admin",
        "admin_email": "iso@isolated.com",
        "admin_password": "SecurePassword2026!"
    }
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 201
    iso_token = res.json()["access_token"]
    iso_org_id = res.json()["organization_id"]

    iso_headers = {
        "Authorization": f"Bearer {iso_token}",
        "X-Organization-Id": iso_org_id
    }

    # Query rules for isolated org: Should have 0 rules initially (not Freshsip's 6 rules)
    rules_res = client.get("/api/v1/knowledge/rules", headers=iso_headers)
    assert rules_res.status_code == 200
    assert len(rules_res.json()) == 0

    # Query content items: Should have 0 drafts (not Freshsip's draft)
    content_res = client.get("/api/v1/content", headers=iso_headers)
    assert content_res.status_code == 200
    assert len(content_res.json()) == 0

    # Attempt to spoof X-Organization-Id to Freshsip org ID
    freshsip_org = client.post("/api/v1/auth/dev-login", json={"role": "org_admin", "organization_slug": "freshsip"}).json()
    freshsip_org_id = freshsip_org["organization_id"]

    spoof_headers = {
        "Authorization": f"Bearer {iso_token}",
        "X-Organization-Id": freshsip_org_id
    }
    spoof_res = client.get("/api/v1/knowledge/rules", headers=spoof_headers)
    assert spoof_res.status_code == 403
    assert "Tenant Isolation" in spoof_res.json()["detail"]
