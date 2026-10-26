from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.organization import User, Organization, OrganizationMembership, OrganizationRole
from app.schemas.auth import UserCreate, UserLogin, UserOut, Token, DevLoginRequest, SwitchOrgRequest
from app.services.auth import verify_password, get_password_hash, create_access_token
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    clean_email = login_data.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

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
        "role": target_membership.role
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=target_membership.role
    )

@router.post("/switch-org", response_model=Token)
def switch_organization(
    req: SwitchOrgRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Safely switch active workspace between organizations the user belongs to.
    Re-mints a fresh JWT token with the target organization's id and role.
    """
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
        "role": target_membership.role
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=target_membership.role
    )

@router.post("/dev-login", response_model=Token)
def dev_login(req: DevLoginRequest, db: Session = Depends(get_db)):
    """
    [DEVELOPMENT ONLY] Fast role switcher for testing all 4 personas in the Freshsip workspace.
    Explicitly restricted in production environments.
    """
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development login bypass is disabled in production."
        )

    # Find the requested role or user
    role_email_map = {
        OrganizationRole.ORG_ADMIN: "admin@freshsip.demo",
        OrganizationRole.KNOWLEDGE_REVIEWER: "reviewer@freshsip.demo",
        OrganizationRole.CONTENT_CREATOR: "creator@freshsip.demo",
        OrganizationRole.APPROVAL_MANAGER: "approver@freshsip.demo"
    }
    target_email = role_email_map.get(req.role, f"{req.role}@freshsip.demo")

    user = db.query(User).filter(User.email == target_email).first()
    if not user:
        # Fallback to any user with this role
        membership = db.query(OrganizationMembership).filter(OrganizationMembership.role == req.role).first()
        if membership:
            user = db.query(User).filter(User.id == membership.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seed user with role '{req.role}' not found. Please run seed script."
        )

    membership = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).first()
    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()

    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": membership.role
    }
    access_token = create_access_token(token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=membership.role
    )

@router.get("/me")
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
        "organizations": org_list
    }
