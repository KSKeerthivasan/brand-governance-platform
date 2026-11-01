import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.database import SessionLocal
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole, OrganizationInvitation
from app.models.brand import Brand
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
def invitation_test_setup(db_session):
    # Setup test org 1
    org1_slug = "inv-test-org-1"
    existing_org = db_session.query(Organization).filter(Organization.slug == org1_slug).first()
    if existing_org:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": existing_org.id})
        db_session.commit()

    org1 = Organization(name="Invite Test Org 1", slug=org1_slug)
    db_session.add(org1)
    db_session.flush()

    admin1 = User(
        email="admin@invtest1.demo",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Org1 Admin",
        is_active=True
    )
    db_session.add(admin1)
    db_session.flush()

    db_session.add(OrganizationMembership(
        organization_id=org1.id,
        user_id=admin1.id,
        role=OrganizationRole.ORG_ADMIN
    ))

    # Reviewer in Org 1 (non-admin)
    reviewer1 = User(
        email="reviewer@invtest1.demo",
        hashed_password=get_password_hash("RevPass123!"),
        full_name="Org1 Reviewer",
        is_active=True
    )
    db_session.add(reviewer1)
    db_session.flush()
    db_session.add(OrganizationMembership(
        organization_id=org1.id,
        user_id=reviewer1.id,
        role=OrganizationRole.KNOWLEDGE_REVIEWER
    ))

    # Setup test org 2 for tenant isolation checks
    org2_slug = "inv-test-org-2"
    existing_org2 = db_session.query(Organization).filter(Organization.slug == org2_slug).first()
    if existing_org2:
        db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": existing_org2.id})
        db_session.commit()

    org2 = Organization(name="Invite Test Org 2", slug=org2_slug)
    db_session.add(org2)
    db_session.flush()

    admin2 = User(
        email="admin@invtest2.demo",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Org2 Admin",
        is_active=True
    )
    db_session.add(admin2)
    db_session.flush()
    db_session.add(OrganizationMembership(
        organization_id=org2.id,
        user_id=admin2.id,
        role=OrganizationRole.ORG_ADMIN
    ))

    db_session.commit()

    admin1_token = create_access_token({
        "sub": admin1.id,
        "email": admin1.email,
        "org_id": org1.id,
        "role": OrganizationRole.ORG_ADMIN,
        "is_demo": False
    })
    reviewer1_token = create_access_token({
        "sub": reviewer1.id,
        "email": reviewer1.email,
        "org_id": org1.id,
        "role": OrganizationRole.KNOWLEDGE_REVIEWER,
        "is_demo": False
    })
    admin2_token = create_access_token({
        "sub": admin2.id,
        "email": admin2.email,
        "org_id": org2.id,
        "role": OrganizationRole.ORG_ADMIN,
        "is_demo": False
    })

    yield {
        "org1": org1,
        "admin1": admin1,
        "admin1_headers": {"Authorization": f"Bearer {admin1_token}", "X-Organization-Id": org1.id},
        "reviewer1_headers": {"Authorization": f"Bearer {reviewer1_token}", "X-Organization-Id": org1.id},
        "org2": org2,
        "admin2": admin2,
        "admin2_headers": {"Authorization": f"Bearer {admin2_token}", "X-Organization-Id": org2.id},
    }

    # Teardown
    try:
        db_session.execute(text("DELETE FROM organizations WHERE id IN (:id1, :id2)"), {"id1": org1.id, "id2": org2.id})
        db_session.commit()
    except Exception:
        pass


def test_invite_member_flow(invitation_test_setup, db_session):
    setup = invitation_test_setup
    org1_id = setup["org1"].id
    admin1_headers = setup["admin1_headers"]

    # 1. Create invitation for content_creator
    payload = {
        "email": "NewCreator@TestDomain.com",
        "role": "content_creator",
        "invitee_name": "New Creator User"
    }
    r = client.post(f"/api/v1/organizations/{org1_id}/invitations", json=payload, headers=admin1_headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["email"] == "newcreator@testdomain.com"
    assert data["role"] == "content_creator"
    assert data["status"] == "pending"
    assert data["delivery_status"] in ("sent", "unconfigured_demo_fallback")
    assert "token=" in data["invitation_link"]
    invitation_id = data["id"]

    # Extract raw token
    raw_token = data["invitation_link"].split("token=")[1]

    # Verify DB record: raw token is NEVER stored in database
    db_inv = db_session.query(OrganizationInvitation).filter(OrganizationInvitation.id == invitation_id).first()
    assert db_inv is not None
    assert db_inv.token_hash != raw_token
    assert len(db_inv.token_hash) == 64  # SHA-256

    # 2. Cannot invite existing member of same org
    r_dup = client.post(
        f"/api/v1/organizations/{org1_id}/invitations",
        json={"email": "reviewer@invtest1.demo", "role": "content_creator"},
        headers=admin1_headers
    )
    assert r_dup.status_code == 409
    assert "already a member" in r_dup.text

    # 3. Non-admin cannot invite
    r_unauth = client.post(
        f"/api/v1/organizations/{org1_id}/invitations",
        json={"email": "someone@test.com", "role": "content_creator"},
        headers=setup["reviewer1_headers"]
    )
    assert r_unauth.status_code == 403

    # 4. Cannot invite into another organization
    r_cross = client.post(
        f"/api/v1/organizations/{setup['org2'].id}/invitations",
        json={"email": "someone@test.com", "role": "content_creator"},
        headers=admin1_headers
    )
    assert r_cross.status_code == 403


def test_token_rotation_on_reinvite(invitation_test_setup, db_session):
    setup = invitation_test_setup
    org1_id = setup["org1"].id
    admin1_headers = setup["admin1_headers"]

    # Re-inviting same pending email rotates the token
    payload = {
        "email": "newcreator@testdomain.com",
        "role": "approval_manager",  # Changed role
        "invitee_name": "Updated Role"
    }
    r = client.post(f"/api/v1/organizations/{org1_id}/invitations", json=payload, headers=admin1_headers)
    assert r.status_code == 201
    rotated = r.json()
    assert rotated["role"] == "approval_manager"
    new_token = rotated["invitation_link"].split("token=")[1]

    # List invitations: should still be only 1 pending invitation for this email
    r_list = client.get(f"/api/v1/organizations/{org1_id}/invitations", headers=admin1_headers)
    assert r_list.status_code == 200
    invs = r_list.json()
    matching = [i for i in invs if i["email"] == "newcreator@testdomain.com"]
    assert len(matching) == 1
    assert matching[0]["role"] == "approval_manager"


def test_verify_and_accept_invitation(invitation_test_setup, db_session):
    setup = invitation_test_setup
    org1 = setup["org1"]
    admin1_headers = setup["admin1_headers"]

    # 1. Create a fresh invitation
    r_inv = client.post(
        f"/api/v1/organizations/{org1.id}/invitations",
        json={"email": "joined.member@testdomain.com", "role": "content_creator"},
        headers=admin1_headers
    )
    assert r_inv.status_code == 201
    inv_data = r_inv.json()
    token = inv_data["invitation_link"].split("token=")[1]

    # 2. Public verification endpoint (no auth headers required)
    r_verify = client.get(f"/api/v1/invitations/verify?token={token}")
    assert r_verify.status_code == 200, r_verify.text
    ver_data = r_verify.json()
    assert ver_data["organization_name"] == org1.name
    assert ver_data["organization_slug"] == org1.slug
    assert ver_data["email"] == "joined.member@testdomain.com"
    assert ver_data["role"] == "content_creator"
    assert ver_data["is_existing_user"] is False

    # 3. Accept invitation for new user
    accept_payload = {
        "token": token,
        "full_name": "Newly Joined Creator",
        "password": "SecurePassword123!"
    }
    r_accept = client.post("/api/v1/invitations/accept", json=accept_payload)
    assert r_accept.status_code == 200, r_accept.text
    login_data = r_accept.json()
    assert login_data["role"] == "content_creator"
    assert login_data["organization_id"] == org1.id
    assert "access_token" in login_data

    # 4. Verify membership created in DB
    new_user = db_session.query(User).filter(User.email == "joined.member@testdomain.com").first()
    assert new_user is not None
    m = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org1.id,
        OrganizationMembership.user_id == new_user.id
    ).first()
    assert m is not None
    assert m.role == "content_creator"

    # 5. Token is now consumed; verify endpoint rejects it
    r_verify_after = client.get(f"/api/v1/invitations/verify?token={token}")
    assert r_verify_after.status_code == 400
    assert "already been accepted" in r_verify_after.text

    # 6. Cannot accept again
    r_accept_again = client.post("/api/v1/invitations/accept", json=accept_payload)
    assert r_accept_again.status_code == 400


def test_revoke_invitation(invitation_test_setup, db_session):
    setup = invitation_test_setup
    org1 = setup["org1"]
    admin1_headers = setup["admin1_headers"]

    # 1. Create invitation
    r_inv = client.post(
        f"/api/v1/organizations/{org1.id}/invitations",
        json={"email": "to_be_revoked@testdomain.com", "role": "knowledge_reviewer"},
        headers=admin1_headers
    )
    assert r_inv.status_code == 201
    inv_id = r_inv.json()["id"]
    token = r_inv.json()["invitation_link"].split("token=")[1]

    # 2. Revoke invitation
    r_rev = client.post(
        f"/api/v1/organizations/{org1.id}/invitations/{inv_id}/revoke",
        headers=admin1_headers
    )
    assert r_rev.status_code == 200
    assert r_rev.json()["status"] == "revoked"

    # 3. Verify public verification fails
    r_verify = client.get(f"/api/v1/invitations/verify?token={token}")
    assert r_verify.status_code == 400
    assert "revoked" in r_verify.text
