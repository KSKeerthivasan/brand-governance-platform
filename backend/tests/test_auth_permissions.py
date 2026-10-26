import pytest

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_login_success(client):
    res = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "content_creator"
    assert data["organization_slug"] == "freshsip"

def test_login_failure(client):
    res = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "WrongPassword123!"
    })
    assert res.status_code == 401

def test_rbac_content_creator_cannot_invite_members(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res = client.post("/api/v1/organizations/members", headers=headers, json={
        "user_email": "newuser@test.com",
        "role": "content_creator"
    })
    # Should be forbidden for non-admin
    assert res.status_code == 403

def test_tenant_isolation_denies_unauthorized_org(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"].copy()
    headers["X-Organization-Id"] = "00000000-0000-0000-0000-000000000000"
    res = client.get("/api/v1/content", headers=headers)
    assert res.status_code == 403
    assert "Tenant Isolation" in res.json()["detail"]
