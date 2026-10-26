from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.organization import User, Organization, OrganizationMembership, OrganizationRole
from app.schemas.auth import UserCreate, UserLogin, UserOut, Token, DevLoginRequest
from app.services.auth import verify_password, get_password_hash, create_access_token
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    membership = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any organization."
        )

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
        user=UserOut.from_orm(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=membership.role
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
        user=UserOut.from_orm(user),
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
        "user": UserOut.from_orm(current_user),
        "organizations": org_list
    }
