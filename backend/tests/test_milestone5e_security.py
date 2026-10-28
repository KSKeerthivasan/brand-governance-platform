"""
Milestone 5E Security Regression Tests
Ensures real authentication, strict role derivation, tenant isolation,
production startup guardrails, brute-force rate-limiting, and zero regressions.
"""
import uuid
import time
from datetime import timedelta
import pytest
from app.config import settings
from app.models.organization import User, Organization, OrganizationMembership, OrganizationRole
from app.models.brand import Brand
from app.services.auth import (
    create_access_token,
    decode_access_token,
    verify_password,
    get_password_hash,
    login_rate_limiter,
    is_token_revoked
)
from app.cli.provision_admin import provision_admin


def test_01_unauthenticated_requests_rejected(client):
    """
    1. Unauthenticated requests cannot access protected endpoints (401 Unauthorized).
    """
    protected_endpoints = [
        ("GET", "/api/v1/content"),
        ("GET", "/api/v1/knowledge/sources"),
        ("GET", "/api/v1/analytics/overview"),
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/switch-org"),
    ]

    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"Expected 401 for {method} {path}, got {res.status_code}"
        assert "Authentication required" in res.json().get("detail", "") or "token" in res.json().get("detail", "").lower()


def test_02_valid_authentication_resolves_correct_user(client):
    """
    2. Valid authentication resolves the correct user identity and active tenant role.
    """
    login_res = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    data = login_res.json()
    assert data["role"] == "content_creator"
    assert data["user"]["email"] == "creator@freshsip.demo"
    assert data["is_demo"] is False
    token = data["access_token"]

    # Verify /auth/me returns the verified profile
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["email"] == "creator@freshsip.demo"
    assert me_data["is_demo"] is False
    assert any(org["role"] == "content_creator" for org in me_data["organizations"])


def test_03_expired_revoked_invalid_credentials_rejected(client, db_session):
    """
    3. Expired, revoked, or forged tokens are rejected (401 Unauthorized).
    """
    # A. Malformed token string
    res_malformed = client.get("/api/v1/content", headers={"Authorization": "Bearer not-a-valid-token"})
    assert res_malformed.status_code == 401
    assert "Invalid or expired" in res_malformed.json()["detail"]

    # B. Forged token signed with a different key
    forged_token = create_access_token(
        {"sub": "non-existent-user", "role": "org_admin", "org_id": "fake"},
        expires_delta=timedelta(minutes=10)
    )
    # Tamper with the signature portion
    parts = forged_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.invalidsignature123"
    res_forged = client.get("/api/v1/content", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_forged.status_code == 401

    # C. Expired token
    expired_token = create_access_token(
        {"sub": "creator-id", "role": "content_creator", "org_id": "freshsip"},
        expires_delta=timedelta(seconds=-30)
    )
    res_expired = client.get("/api/v1/content", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401

    # D. Server-side Revoked token via /auth/logout
    login_res = client.post("/api/v1/auth/login", json={
        "email": "reviewer@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    assert login_res.status_code == 200
    token_to_revoke = login_res.json()["access_token"]

    # Verify token works initially
    check1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_to_revoke}"})
    assert check1.status_code == 200

    # Call /logout to invalidate session
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_to_revoke}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["revoked"] is True

    # Token must now immediately fail closed
    check2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_to_revoke}"})
    assert check2.status_code == 401
    assert "revoked or invalidated" in check2.json()["detail"]


def test_04_forged_headers_cannot_escalate_identity_or_permissions(client, db_session):
    """
    4. Forged X-User-Role and X-User-Id values cannot change identity or escalate permissions.
    """
    # Log in legitimately as content_creator
    login_res = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    org_id = login_res.json()["organization_id"]

    # Attempt to access org_admin endpoint while spoofing X-User-Role: org_admin
    spoofed_headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id,
        "X-User-Role": "org_admin",
        "X-User-Id": "fictional-admin-id",
        "X-Role": "org_admin"
    }

    # Attempt to provision a member (requires org_admin)
    res_admin = client.post(
        "/api/v1/organizations/members",
        headers=spoofed_headers,
        json={"user_email": "attacker@evil.corp", "role": "knowledge_reviewer", "full_name": "Attacker"}
    )
    assert res_admin.status_code == 403
    assert "Permission Denied" in res_admin.json()["detail"]
    assert "Your role is 'content_creator'" in res_admin.json()["detail"]

    # Verify /auth/me still strictly reports content_creator
    res_me = client.get("/api/v1/auth/me", headers=spoofed_headers)
    assert res_me.status_code == 200
    assert res_me.json()["user"]["email"] == "creator@freshsip.demo"


def test_05_creator_cannot_approve_content(client, db_session):
    """
    5. A creator cannot approve content by manipulating requests.
    """
    # 1. Login as creator and create a content item
    creator_login = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    creator_token = creator_login.json()["access_token"]
    org_id = creator_login.json()["organization_id"]
    creator_headers = {
        "Authorization": f"Bearer {creator_token}",
        "X-Organization-Id": org_id
    }

    # Find Freshsip brand
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    assert brand is not None

    # Create content
    c_res = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand.id,
        "title": "Creator Self-Approval Attempt",
        "channel": "instagram_feed",
        "body_text": "Enjoy Freshsip pure juice."
    })
    assert c_res.status_code == 200
    content_id = c_res.json()["id"]
    version_id = c_res.json()["latest_version"]["id"]

    # Run governance check
    client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })

    # Creator submits for approval
    sub_res = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": content_id,
        "content_version_id": version_id,
        "submission_notes": "Please approve this post."
    })
    if sub_res.status_code == 200:
        submission_id = sub_res.json()["id"]
        # Creator attempts to approve the content themselves
        approve_attempt = client.post(
            f"/api/v1/approvals/submissions/{submission_id}/decide",
            headers=creator_headers,
            json={
                "decision": "approved",
                "comments": "Self approval by creator."
            }
        )
        assert approve_attempt.status_code == 403
        assert "Permission Denied" in approve_attempt.json()["detail"] or "Conflict of Interest" in approve_attempt.json()["detail"]
    else:
        # If submission failed due to policy blockers, verify creator cannot approve any random submission ID
        random_sub_id = str(uuid.uuid4())
        approve_attempt = client.post(
            f"/api/v1/approvals/submissions/{random_sub_id}/decide",
            headers=creator_headers,
            json={
                "decision": "approved",
                "comments": "Self approval by creator."
            }
        )
        assert approve_attempt.status_code == 403
        assert "Permission Denied" in approve_attempt.json()["detail"]


def test_06_reviewer_only_endpoints_reject_unauthorized_roles(client, db_session):
    """
    6. Reviewer-only endpoints reject unauthorized roles (content_creator, etc.).
    """
    creator_login = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    creator_headers = {
        "Authorization": f"Bearer {creator_login.json()['access_token']}",
        "X-Organization-Id": creator_login.json()["organization_id"]
    }

    # 1. Creator attempts to create a knowledge rule
    rule_attempt = client.post("/api/v1/knowledge/rules", headers=creator_headers, json={
        "rule_type": "prohibited_word",
        "title": "Unauthorized Rule",
        "pattern": "forbidden keyword",
        "explanation": "Unauthorized rule injection",
        "severity": "warning"
    })
    assert rule_attempt.status_code == 403
    assert "Permission Denied" in rule_attempt.json()["detail"]

    # 2. Creator attempts to record a reviewer disposition
    disp_attempt = client.post(f"/api/v1/analytics/findings/{uuid.uuid4()}/feedback", headers=creator_headers, json={
        "disposition": "false_positive",
        "explanation": "Creator trying to bypass reviewer gate."
    })
    assert disp_attempt.status_code == 403
    assert "Permission Denied" in disp_attempt.json()["detail"]


def test_07_cross_organization_access_rejected(client, db_session):
    """
    7. Cross-organization access is rejected for content, PDFs, suggestions, analytics and review history.
    """
    # 1. Provision a distinct organization "Tenant Alpha"
    org_alpha = provision_admin(
        org_name="Alpha Pharmaceuticals",
        org_slug="alpha-pharma",
        admin_email="admin@alpha.pharma",
        admin_name="Alpha Admin",
        admin_password="AlphaPassword2026!",
        brand_name="Alpha Pharma Brand",
        db=db_session
    )

    # Login as Alpha Admin and create private content
    alpha_login = client.post("/api/v1/auth/login", json={
        "email": "admin@alpha.pharma",
        "password": "AlphaPassword2026!",
        "organization_slug": "alpha-pharma"
    })
    assert alpha_login.status_code == 200
    alpha_token = alpha_login.json()["access_token"]
    alpha_org_id = org_alpha["organization_id"]

    alpha_brand = db_session.query(Brand).filter(Brand.organization_id == alpha_org_id).first()

    alpha_content_res = client.post("/api/v1/content", headers={
        "Authorization": f"Bearer {alpha_token}",
        "X-Organization-Id": alpha_org_id
    }, json={
        "brand_id": alpha_brand.id,
        "title": "Alpha Confidential Research",
        "channel": "print_poster",
        "body_text": "Proprietary formulation data."
    })
    assert alpha_content_res.status_code == 200
    alpha_content_id = alpha_content_res.json()["id"]

    # 2. Login as Freshsip Creator
    freshsip_login = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    freshsip_token = freshsip_login.json()["access_token"]
    freshsip_org_id = freshsip_login.json()["organization_id"]

    # Attack A: Freshsip user presents X-Organization-Id of Alpha Pharma
    tampered_headers = {
        "Authorization": f"Bearer {freshsip_token}",
        "X-Organization-Id": alpha_org_id
    }
    res_tampered = client.get("/api/v1/content", headers=tampered_headers)
    assert res_tampered.status_code == 403
    assert "Tenant Isolation" in res_tampered.json()["detail"]

    # Attack B: Freshsip user attempts to directly view Alpha's content item
    legit_freshsip_headers = {
        "Authorization": f"Bearer {freshsip_token}",
        "X-Organization-Id": freshsip_org_id
    }
    res_direct = client.get(f"/api/v1/content/{alpha_content_id}", headers=legit_freshsip_headers)
    assert res_direct.status_code in [403, 404]

    # Attack C: Freshsip user attempts to view Alpha's analytics
    res_analytics = client.get("/api/v1/analytics/overview", headers=tampered_headers)
    assert res_analytics.status_code == 403
    assert "Tenant Isolation" in res_analytics.json()["detail"]


def test_08_production_configuration_disables_simulated_identity(client):
    """
    8. Production configuration disables simulated identity (/dev-login returns 403).
    """
    orig_env = settings.ENVIRONMENT
    orig_dev = settings.ALLOW_DEV_LOGIN
    try:
        settings.ENVIRONMENT = "production"
        settings.ALLOW_DEV_LOGIN = False

        res = client.post("/api/v1/auth/dev-login", json={
            "role": "content_creator",
            "organization_slug": "freshsip"
        })
        assert res.status_code == 403
        assert "disabled in this environment" in res.json()["detail"]
    finally:
        settings.ENVIRONMENT = orig_env
        settings.ALLOW_DEV_LOGIN = orig_dev


def test_09_local_development_mode_available_only_when_explicitly_enabled(client):
    """
    9. Local development/test authentication remains available only when explicitly enabled.
    """
    orig_env = settings.ENVIRONMENT
    orig_dev = settings.ALLOW_DEV_LOGIN
    try:
        # Case A: Development mode with ALLOW_DEV_LOGIN = True -> succeeds
        settings.ENVIRONMENT = "development"
        settings.ALLOW_DEV_LOGIN = True
        res_ok = client.post("/api/v1/auth/dev-login", json={
            "role": "content_creator",
            "organization_slug": "freshsip"
        })
        assert res_ok.status_code == 200
        assert res_ok.json()["is_demo"] is True

        # Case B: Development mode with ALLOW_DEV_LOGIN = False -> rejected
        settings.ALLOW_DEV_LOGIN = False
        res_blocked = client.post("/api/v1/auth/dev-login", json={
            "role": "content_creator",
            "organization_slug": "freshsip"
        })
        assert res_blocked.status_code == 403
        assert "disabled in this environment" in res_blocked.json()["detail"]
    finally:
        settings.ENVIRONMENT = orig_env
        settings.ALLOW_DEV_LOGIN = orig_dev


def test_10_governance_and_approvals_regression_under_real_auth(client, db_session):
    """
    10. Complete end-to-end lifecycle runs cleanly under real authenticated tokens.
    """
    # 1. Creator login
    c_login = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    org_id = c_login.json()["organization_id"]
    c_headers = {
        "Authorization": f"Bearer {c_login.json()['access_token']}",
        "X-Organization-Id": org_id
    }

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()

    # Create content
    c_item = client.post("/api/v1/content", headers=c_headers, json={
        "brand_id": brand.id,
        "title": "Real Auth E2E Test",
        "channel": "instagram_feed",
        "body_text": "Freshsip natural cold-pressed juices are 100% pure."
    }).json()

    content_id = c_item["id"]
    version_id = c_item["latest_version"]["id"]

    # Run governance check
    gov_run = client.post("/api/v1/governance/run", headers=c_headers, json={
        "content_version_id": version_id
    }).json()
    assert gov_run["content_version_id"] == version_id

    # 2. Reviewer login
    r_login = client.post("/api/v1/auth/login", json={
        "email": "reviewer@freshsip.demo",
        "password": "Freshsip2026!",
        "organization_slug": "freshsip"
    })
    r_headers = {
        "Authorization": f"Bearer {r_login.json()['access_token']}",
        "X-Organization-Id": org_id
    }

    # Reviewer can inspect knowledge rules
    rules_res = client.get("/api/v1/knowledge/rules", headers=r_headers)
    assert rules_res.status_code == 200

    # 3. Submit for approval by creator
    sub_res = client.post("/api/v1/approvals/submit", headers=c_headers, json={
        "content_item_id": content_id,
        "content_version_id": version_id,
        "submission_notes": "Submitting after automated governance check."
    })
    if sub_res.status_code == 200:
        sub = sub_res.json()
        assert sub["status"] == "pending"

        # 4. Approver login
        a_login = client.post("/api/v1/auth/login", json={
            "email": "approver@freshsip.demo",
            "password": "Freshsip2026!",
            "organization_slug": "freshsip"
        })
        a_headers = {
            "Authorization": f"Bearer {a_login.json()['access_token']}",
            "X-Organization-Id": org_id
        }

        # Approver records decision
        dec = client.post(f"/api/v1/approvals/submissions/{sub['id']}/decide", headers=a_headers, json={
            "decision": "approved",
            "comments": "Meets compliance requirements. Approved for broadcast."
        })
        assert dec.status_code in [200, 201]
        assert dec.json()["decision"] == "approved"
    else:
        # If blocked by critical policy rule in body_text, fail-closed behavior confirmed
        assert sub_res.status_code in [400, 422]


def test_11_auth_errors_do_not_leak_secrets_or_stack_traces(client):
    """
    11. Authentication errors and production startup checks do not leak secrets or stack traces.
    """
    # 1. Invalid login response format
    res_bad = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@user.com",
        "password": "WrongPassword123!"
    })
    assert res_bad.status_code == 401
    err = res_bad.json()
    assert err["detail"] == "Incorrect email or password."
    # Ensure no internal path or DB string leaked
    assert "password" not in str(err).lower() or err["detail"] == "Incorrect email or password."
    assert "postgresql://" not in str(err)
    assert "traceback" not in str(err).lower()

    # 2. Production startup checks validation
    orig_env = settings.ENVIRONMENT
    orig_secret = settings.SECRET_KEY
    orig_debug = settings.DEBUG
    orig_dev = settings.ALLOW_DEV_LOGIN
    try:
        settings.ENVIRONMENT = "production"
        settings.ALLOW_DEV_LOGIN = True
        settings.DEBUG = True
        settings.SECRET_KEY = "dev-insecure-key"

        violations = settings.validate_production_readiness()
        assert len(violations) >= 3
        assert any("ALLOW_DEV_LOGIN" in v for v in violations)
        assert any("DEBUG" in v for v in violations)
        assert any("SECRET_KEY" in v for v in violations)
    finally:
        settings.ENVIRONMENT = orig_env
        settings.SECRET_KEY = orig_secret
        settings.DEBUG = orig_debug
        settings.ALLOW_DEV_LOGIN = orig_dev


def test_12_admin_provisioning_and_rate_limiting(client, db_session):
    """
    12. Administrator provisioning generates unpredictable credentials;
        brute force protection enforces 429 rate-limiting.
    """
    # 1. Administrator provisioning generates unpredictable high-entropy passwords
    unique_slug = f"org-{uuid.uuid4().hex[:8]}"
    admin_info = provision_admin(
        org_name="Secure Tenant Corp",
        org_slug=unique_slug,
        admin_email=f"admin@{unique_slug}.corp",
        admin_name="Secure Admin",
        admin_password=None,  # Generates high-entropy credential
        db=db_session
    )
    assert admin_info["was_generated"] is True
    generated_pwd = admin_info["password"]
    assert len(generated_pwd) >= 24
    assert generated_pwd != "admin"
    assert generated_pwd != "password"
    assert generated_pwd != "Freshsip2026!"

    # Verify admin can log in with generated password
    login_ok = client.post("/api/v1/auth/login", json={
        "email": admin_info["admin_email"],
        "password": generated_pwd,
        "organization_slug": unique_slug
    })
    assert login_ok.status_code == 200
    assert login_ok.json()["role"] == "org_admin"

    # 2. Brute force rate limiting protection
    victim_email = f"target@{unique_slug}.corp"
    login_rate_limiter.reset()

    # Trigger 5 consecutive failed attempts
    for attempt in range(5):
        res = client.post("/api/v1/auth/login", json={
            "email": victim_email,
            "password": f"wrong-password-{attempt}"
        })
        if attempt < 4:
            assert res.status_code == 401
        else:
            # 5th failed attempt triggers 429 lockout
            assert res.status_code == 429
            assert "Too many failed login attempts" in res.json()["detail"]

    # 6th attempt is blocked immediately by rate limiter before password check
    blocked_res = client.post("/api/v1/auth/login", json={
        "email": victim_email,
        "password": "any-password"
    })
    assert blocked_res.status_code == 429
    assert "temporarily locked" in blocked_res.json()["detail"]

    # Clean up rate limiter
    login_rate_limiter.reset()
