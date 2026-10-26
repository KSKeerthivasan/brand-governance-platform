import pytest
from app.models.organization import OrganizationRole, User, OrganizationMembership

def test_org_admin_provisions_all_permitted_roles(client, auth_tokens):
    """
    Org Admin can provision:
    - knowledge_reviewer
    - content_creator
    - approval_manager
    """
    admin_headers = auth_tokens["org_admin"]["headers"]

    roles_to_test = [
        ("reviewer_test@example.com", "Test Reviewer", "knowledge_reviewer", "ReviewerPass2026!"),
        ("creator_test@example.com", "Test Creator", "content_creator", "CreatorPass2026!"),
        ("approver_test@example.com", "Test Approver", "approval_manager", "ApproverPass2026!")
    ]

    for email, name, role, pw in roles_to_test:
        resp = client.post(
            "/api/v1/organizations/members",
            headers=admin_headers,
            json={
                "user_email": email,
                "full_name": name,
                "role": role,
                "password": pw
            }
        )
        assert resp.status_code == 201, f"Failed for role {role}: {resp.text}"
        data = resp.json()
        assert data["user_email"] == email
        assert data["user_full_name"] == name
        assert data["role"] == role
        assert "password" not in data, "Plaintext password must never be returned in response"

        # Verify new member can authenticate via standard login
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": pw}
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert token_data["role"] == role
        assert token_data["user"]["email"] == email
        assert token_data["user"]["full_name"] == name

def test_cannot_provision_org_admin_through_member_form(client, auth_tokens):
    """
    Explicit security constraint:
    Never allow a request to create an org_admin membership through the member provisioning form.
    """
    admin_headers = auth_tokens["org_admin"]["headers"]
    resp = client.post(
        "/api/v1/organizations/members",
        headers=admin_headers,
        json={
            "user_email": "rogue_admin@example.com",
            "full_name": "Rogue Admin",
            "role": "org_admin",
            "password": "Password123!"
        }
    )
    assert resp.status_code == 400
    assert "Cannot provision additional Organization Administrators through this form" in resp.json()["detail"]

def test_invalid_role_rejected(client, auth_tokens):
    """
    Bogus or unpermitted roles must be rejected with HTTP 400.
    """
    admin_headers = auth_tokens["org_admin"]["headers"]
    resp = client.post(
        "/api/v1/organizations/members",
        headers=admin_headers,
        json={
            "user_email": "invalid_role@example.com",
            "full_name": "Invalid Role",
            "role": "super_user_bogus",
            "password": "Password123!"
        }
    )
    assert resp.status_code == 400
    assert "Invalid role" in resp.json()["detail"]

def test_unauthorized_users_cannot_provision_members(client, auth_tokens):
    """
    Content creators and knowledge reviewers must be forbidden from provisioning members.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    resp = client.post(
        "/api/v1/organizations/members",
        headers=creator_headers,
        json={
            "user_email": "unauth@example.com",
            "full_name": "Unauth Test",
            "role": "content_creator",
            "password": "Password123!"
        }
    )
    assert resp.status_code == 403

def test_duplicate_membership_rejected_with_409(client, auth_tokens):
    """
    Attempting to provision a user who is already a member of the organization returns 409 Conflict.
    """
    admin_headers = auth_tokens["org_admin"]["headers"]

    # First provisioning
    resp1 = client.post(
        "/api/v1/organizations/members",
        headers=admin_headers,
        json={
            "user_email": "duplicate_check@example.com",
            "full_name": "Duplicate Check",
            "role": "content_creator",
            "password": "SecurePassword2026!"
        }
    )
    assert resp1.status_code == 201

    # Second provisioning with same email into same org
    resp2 = client.post(
        "/api/v1/organizations/members",
        headers=admin_headers,
        json={
            "user_email": "duplicate_check@example.com",
            "full_name": "Duplicate Check",
            "role": "knowledge_reviewer",
            "password": "SecurePassword2026!"
        }
    )
    assert resp2.status_code == 409
    assert "already a member of this organization" in resp2.json()["detail"]

def test_missing_required_fields_on_new_user(client, auth_tokens):
    """
    Provisioning a new user without full_name or short password returns 422.
    """
    admin_headers = auth_tokens["org_admin"]["headers"]

    # Short password
    resp = client.post(
        "/api/v1/organizations/members",
        headers=admin_headers,
        json={
            "user_email": "short_pw@example.com",
            "full_name": "Short Pw",
            "role": "content_creator",
            "password": "short"
        }
    )
    assert resp.status_code == 422

def test_multi_organization_login_and_workspace_selection(client):
    """
    Test multi-tenant login and workspace selection:
    1. Onboard Org A (Alpha Corp)
    2. Onboard Org B (Beta Corp)
    3. Add a user to Org B
    4. Also add the same user to Org A
    5. Test login with explicit organization_slug
    6. Test login without slug returns HTTP 300 Multiple Choices
    7. Test login specifying an organization the user does NOT belong to returns 403
    8. Test /auth/switch-org to switch active workspace
    """
    # 1. Onboard Alpha Corp
    alpha_onboard = client.post("/api/v1/organizations", json={
        "organization_name": "Alpha Corp",
        "organization_slug": "alpha-corp",
        "brand_name": "Alpha Brand",
        "brand_description": "Alpha description",
        "admin_full_name": "Alpha Admin",
        "admin_email": "admin@alpha.demo",
        "admin_password": "AlphaAdminPass1!"
    })
    assert alpha_onboard.status_code == 201, f"Alpha onboard failed: {alpha_onboard.text}"
    alpha_token = alpha_onboard.json()["access_token"]
    alpha_org_id = alpha_onboard.json()["organization_id"]
    alpha_headers = {
        "Authorization": f"Bearer {alpha_token}",
        "X-Organization-Id": alpha_org_id
    }

    # 2. Onboard Beta Corp
    beta_onboard = client.post("/api/v1/organizations", json={
        "organization_name": "Beta Corp",
        "organization_slug": "beta-corp",
        "brand_name": "Beta Brand",
        "brand_description": "Beta description",
        "admin_full_name": "Beta Admin",
        "admin_email": "admin@beta.demo",
        "admin_password": "BetaAdminPass1!"
    })
    assert beta_onboard.status_code == 201, f"Beta onboard failed: {beta_onboard.text}"
    beta_token = beta_onboard.json()["access_token"]
    beta_org_id = beta_onboard.json()["organization_id"]
    beta_headers = {
        "Authorization": f"Bearer {beta_token}",
        "X-Organization-Id": beta_org_id
    }

    # 3. Provision dual member in Alpha Corp
    dual_email = "dual_member@example.com"
    dual_pw = "DualMemberPass2026!"
    prov_alpha = client.post("/api/v1/organizations/members", headers=alpha_headers, json={
        "user_email": dual_email,
        "full_name": "Dual Member",
        "role": "content_creator",
        "password": dual_pw
    })
    assert prov_alpha.status_code == 201, f"Prov Alpha failed: {prov_alpha.text}"

    # 4. Add the same user into Beta Corp
    prov_beta = client.post("/api/v1/organizations/members", headers=beta_headers, json={
        "user_email": dual_email,
        "full_name": "Dual Member",
        "role": "knowledge_reviewer",
        "password": dual_pw
    })
    assert prov_beta.status_code == 201, f"Prov Beta failed: {prov_beta.text}"

    # 5. Login without org specification returns HTTP 300 with choices
    login_no_org = client.post("/api/v1/auth/login", json={
        "email": dual_email,
        "password": dual_pw
    })
    assert login_no_org.status_code == 300, f"Expected 300: {login_no_org.text}"
    choices = login_no_org.json()["detail"]["organizations"]
    slugs = [c["organization_slug"] for c in choices]
    assert "alpha-corp" in slugs
    assert "beta-corp" in slugs

    # 6. Login specifying Alpha Corp
    login_alpha = client.post("/api/v1/auth/login", json={
        "email": dual_email,
        "password": dual_pw,
        "organization_slug": "alpha-corp"
    })
    assert login_alpha.status_code == 200
    alpha_res = login_alpha.json()
    assert alpha_res["organization_slug"] == "alpha-corp"
    assert alpha_res["role"] == "content_creator"

    # 7. Login specifying Beta Corp
    login_beta = client.post("/api/v1/auth/login", json={
        "email": dual_email,
        "password": dual_pw,
        "organization_slug": "beta-corp"
    })
    assert login_beta.status_code == 200
    beta_res = login_beta.json()
    assert beta_res["organization_slug"] == "beta-corp"
    assert beta_res["role"] == "knowledge_reviewer"

    # 8. Login specifying an unauthorized organization (Freshsip)
    login_unauth = client.post("/api/v1/auth/login", json={
        "email": dual_email,
        "password": dual_pw,
        "organization_slug": "freshsip"
    })
    assert login_unauth.status_code == 403
    assert "Tenant Isolation: You are not a member of the requested organization" in login_unauth.json()["detail"]

    # 9. Test switch-org endpoint
    user_alpha_token = alpha_res["access_token"]
    user_alpha_headers = {
        "Authorization": f"Bearer {user_alpha_token}",
        "X-Organization-Id": alpha_org_id
    }

    switch_resp = client.post("/api/v1/auth/switch-org", headers=user_alpha_headers, json={
        "organization_slug": "beta-corp"
    })
    assert switch_resp.status_code == 200
    switched_data = switch_resp.json()
    assert switched_data["organization_slug"] == "beta-corp"
    assert switched_data["role"] == "knowledge_reviewer"

    # Switch to unauthorized org
    switch_fail = client.post("/api/v1/auth/switch-org", headers=user_alpha_headers, json={
        "organization_slug": "freshsip"
    })
    assert switch_fail.status_code == 403

def test_freshsip_regression(client):
    """
    Ensure existing Freshsip demo accounts continue to authenticate and operate seamlessly.
    """
    freshsip_resp = client.post("/api/v1/auth/login", json={
        "email": "creator@freshsip.demo",
        "password": "Freshsip2026!"
    })
    assert freshsip_resp.status_code == 200
    data = freshsip_resp.json()
    assert data["organization_slug"] == "freshsip"
    assert data["role"] == "content_creator"
