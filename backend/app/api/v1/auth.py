from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.organization import User, Organization, OrganizationMembership, OrganizationRole
from app.schemas.auth import UserCreate, UserLogin, UserOut, Token, DevLoginRequest, SwitchOrgRequest
from app.services.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    revoke_token,
    login_rate_limiter
)
from app.api.deps import get_current_user, security

router = APIRouter()

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates user credentials, enforces brute-force rate-limiting,
    and returns a signed JWT access token bound to the selected organization.
    """
    clean_email = login_data.email.strip().lower()

    # 1. Enforce brute-force rate limiter before processing
    is_locked, remaining_sec = login_rate_limiter.is_locked_out(clean_email)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Account temporarily locked for {remaining_sec} seconds."
        )

    # 2. Verify credentials
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        locked_now, info = login_rate_limiter.record_failure(clean_email)
        if locked_now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Account temporarily locked for {info} seconds."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    # 3. Check account active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or disabled."
        )

    # 4. Success: reset rate limit tracking
    login_rate_limiter.record_success(clean_email)

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id
    ).all()
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any organization."
        )

    target_membership = None

    if login_data.organization_id:
        target_membership = next((m for m in memberships if m.organization_id == login_data.organization_id), None)
        if not target_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant Isolation: You are not a member of the requested organization."
            )
    elif login_data.organization_slug:
        org = db.query(Organization).filter(Organization.slug == login_data.organization_slug.strip().lower()).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with slug '{login_data.organization_slug}' not found."
            )
        target_membership = next((m for m in memberships if m.organization_id == org.id), None)
        if not target_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant Isolation: You are not a member of the requested organization."
            )
    else:
        if len(memberships) == 1:
            target_membership = memberships[0]
        else:
            org_options = []
            for m in memberships:
                o = db.query(Organization).filter(Organization.id == m.organization_id).first()
                if o:
                    org_options.append({
                        "organization_id": o.id,
                        "organization_name": o.name,
                        "organization_slug": o.slug,
                        "role": m.role
                    })
            raise HTTPException(
                status_code=status.HTTP_300_MULTIPLE_CHOICES,
                detail={
                    "message": "Multiple organizations found. Please specify organization_id or organization_slug.",
                    "organizations": org_options
                }
            )

    org = db.query(Organization).filter(Organization.id == target_membership.organization_id).first()

    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": target_membership.role,
        "is_demo": False
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=target_membership.role,
        is_demo=False
    )

@router.post("/logout")
def logout(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Server-side session invalidation (Milestone 5E).
    Revokes the caller's JWT token by adding its jti to the revoked_tokens registry.
    Any subsequent request presenting this token will fail closed with 401 Unauthorized.
    """
    if not auth_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to log out."
        )
    token = auth_credentials.credentials
    success = revoke_token(db, token, reason="user_logout")
    return {
        "status": "success",
        "message": "Successfully logged out. Session credentials have been invalidated.",
        "revoked": success
    }

@router.post("/switch-org", response_model=Token)
def switch_organization(
    req: SwitchOrgRequest,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Safely switch active workspace between organizations the user belongs to.
    Re-mints a fresh JWT token with the target organization's id and role.
    """
    token_str = auth_credentials.credentials if auth_credentials else None
    prev_payload = decode_access_token(token_str) if token_str else {}
    is_demo = bool(prev_payload.get("is_demo", False))

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == current_user.id
    ).all()

    target_membership = None
    if req.organization_id:
        target_membership = next((m for m in memberships if m.organization_id == req.organization_id), None)
    elif req.organization_slug:
        org = db.query(Organization).filter(Organization.slug == req.organization_slug.strip().lower()).first()
        if org:
            target_membership = next((m for m in memberships if m.organization_id == org.id), None)

    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant Isolation: You are not a member of the requested organization."
        )

    org = db.query(Organization).filter(Organization.id == target_membership.organization_id).first()
    token_payload = {
        "sub": current_user.id,
        "email": current_user.email,
        "org_id": org.id,
        "role": target_membership.role,
        "is_demo": is_demo
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=target_membership.role,
        is_demo=is_demo
    )

@router.post("/dev-login", response_model=Token)
def dev_login(req: DevLoginRequest, db: Session = Depends(get_db)):
    """
    [DEVELOPMENT ONLY] Fast persona switcher for testing all 4 personas in the Freshsip workspace.
    Explicitly disabled in production or when ALLOW_DEV_LOGIN is false.
    """
    if settings.ENVIRONMENT.lower() == "production" or not settings.ALLOW_DEV_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development login bypass is disabled in this environment."
        )

    target_org = None
    if req.organization_slug:
        target_org = db.query(Organization).filter(Organization.slug == req.organization_slug.strip().lower()).first()

    # Find the requested role or user
    role_email_map = {
        OrganizationRole.ORG_ADMIN: "admin@freshsip.demo",
        OrganizationRole.KNOWLEDGE_REVIEWER: "reviewer@freshsip.demo",
        OrganizationRole.CONTENT_CREATOR: "creator@freshsip.demo",
        OrganizationRole.APPROVAL_MANAGER: "approver@freshsip.demo"
    }
    target_email = role_email_map.get(req.role, f"{req.role}@freshsip.demo")

    user = None
    if target_org:
        # Check if the target email belongs to this organization
        target_user = db.query(User).filter(User.email == target_email).first()
        if target_user:
            has_mem = db.query(OrganizationMembership).filter(
                OrganizationMembership.user_id == target_user.id,
                OrganizationMembership.organization_id == target_org.id
            ).first()
            if has_mem:
                user = target_user

    if not user:
        user = db.query(User).filter(User.email == target_email).first()

    if not user:
        # Fallback to any user with this role within the target organization
        mem_q = db.query(OrganizationMembership).filter(OrganizationMembership.role == req.role)
        if target_org:
            mem_q = mem_q.filter(OrganizationMembership.organization_id == target_org.id)
        membership = mem_q.first()
        if membership:
            user = db.query(User).filter(User.id == membership.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with role '{req.role}' for organization '{req.organization_slug}' not found."
        )

    mem_q = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id)
    if target_org:
        mem_q = mem_q.filter(OrganizationMembership.organization_id == target_org.id)
    membership = mem_q.first()
    org = target_org or db.query(Organization).filter(Organization.id == membership.organization_id).first()

    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": membership.role,
        "is_demo": True
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=membership.role,
        is_demo=True
    )

@router.get("/me")
def get_current_user_profile(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token_str = auth_credentials.credentials if auth_credentials else None
    token_payload = decode_access_token(token_str) if token_str else {}
    is_demo = bool(token_payload.get("is_demo", False))

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == current_user.id
    ).all()

    org_list = []
    for m in memberships:
        org = db.query(Organization).filter(Organization.id == m.organization_id).first()
        if org:
            org_list.append({
                "organization_id": org.id,
                "organization_name": org.name,
                "organization_slug": org.slug,
                "role": m.role
            })

    return {
        "user": UserOut.model_validate(current_user),
        "organizations": org_list,
        "is_demo": is_demo
    }
