from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import (
    Organization, OrganizationMembership, User, OrganizationRole, OrganizationInvitation
)
from app.models.brand import Brand
from app.schemas.organization import (
    OrganizationOut, MembershipOut, MembershipCreate, OrganizationOnboard,
    InvitationCreate, InvitationOut
)
from app.schemas.auth import Token, UserOut
from app.services.auth import get_password_hash, create_access_token
from app.api.deps import get_current_user, require_org_admin, require_any_member
from app.services.audit import log_audit_event
from app.services.invitation_service import invitation_service

router = APIRouter()

@router.post("", response_model=Token, status_code=status.HTTP_201_CREATED)
def onboard_organization(
    req: OrganizationOnboard,
    db: Session = Depends(get_db)
):
    """
    Onboard a brand-new organization and its initial administrator.
    Transactionally creates:
    1. Organization
    2. Initial Brand
    3. Administrator User (with bcrypt password hash)
    4. Organization Administrator (org_admin) Membership
    5. Initialization Audit Log Event
    Returns authenticated session Token with immediate workspace access.
    """
    # 1. Check duplicate organization slug
    existing_org = db.query(Organization).filter(
        Organization.slug == req.organization_slug
    ).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{req.organization_slug}' already exists. Please choose a different slug."
        )

    # 2. Check duplicate admin email
    clean_email = req.admin_email.strip().lower()
    existing_user = db.query(User).filter(
        User.email == clean_email
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{clean_email}' already exists. Please sign in or use a different email."
        )

    try:
        # Create organization
        org = Organization(
            name=req.organization_name.strip(),
            slug=req.organization_slug.strip()
        )
        db.add(org)
        db.flush()

        # Create initial brand
        brand = Brand(
            organization_id=org.id,
            name=req.brand_name.strip(),
            description=req.brand_description.strip() if req.brand_description else None
        )
        db.add(brand)
        db.flush()

        # Create admin user
        user = User(
            email=clean_email,
            hashed_password=get_password_hash(req.admin_password),
            full_name=req.admin_full_name.strip(),
            is_active=True
        )
        db.add(user)
        db.flush()

        # Create membership as Org Admin
        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=OrganizationRole.ORG_ADMIN
        )
        db.add(membership)
        db.flush()

        # Log audit event
        log_audit_event(
            db=db,
            organization_id=org.id,
            user_id=user.id,
            event_type="ORGANIZATION_ONBOARDED",
            entity_type="organization",
            entity_id=org.id,
            summary=f"Onboarded organization '{org.name}' with initial brand '{brand.name}' and Org Admin '{user.full_name}'",
            details={
                "slug": org.slug,
                "brand": brand.name,
                "admin_email": user.email
            }
        )

        db.commit()
        db.refresh(org)
        db.refresh(user)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transaction failure during onboarding: {str(e)}"
        )

    # Generate JWT token
    token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "org_id": org.id,
            "role": OrganizationRole.ORG_ADMIN,
            "is_demo": False
        }
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=OrganizationRole.ORG_ADMIN,
        is_demo=False
    )

@router.get("/current", response_model=OrganizationOut)
def get_current_org(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    return org

@router.get("/members", response_model=List[MembershipOut])
def list_org_members(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == membership.organization_id
    ).all()

    result = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append(MembershipOut(
            id=m.id,
            organization_id=m.organization_id,
            user_id=m.user_id,
            user_email=user.email if user else "unknown",
            user_full_name=user.full_name if user else "Unknown User",
            role=m.role,
            created_at=m.created_at
        ))
    return result

PERMITTED_PROVISION_ROLES = [
    OrganizationRole.KNOWLEDGE_REVIEWER,
    OrganizationRole.CONTENT_CREATOR,
    OrganizationRole.APPROVAL_MANAGER
]

@router.post("/members", response_model=MembershipOut, status_code=status.HTTP_201_CREATED)
def add_org_member(
    req: MembershipCreate,
    membership: OrganizationMembership = Depends(require_org_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Enforce strict role boundary: org_admin cannot be provisioned via member form
    if req.role == OrganizationRole.ORG_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot provision additional Organization Administrators through this form. Permitted roles: knowledge_reviewer, content_creator, approval_manager."
        )

    if req.role not in PERMITTED_PROVISION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{req.role}'. Permitted roles: {', '.join(PERMITTED_PROVISION_ROLES)}"
        )

    clean_email = req.user_email.strip().lower()

    # 2. Check if user already exists
    user = db.query(User).filter(User.email == clean_email).first()

    if user:
        # Check if already a member of this organization
        existing_m = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == membership.organization_id,
            OrganizationMembership.user_id == user.id
        ).first()
        if existing_m:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{clean_email}' is already a member of this organization with role '{existing_m.role}'."
            )

        target_membership = OrganizationMembership(
            organization_id=membership.organization_id,
            user_id=user.id,
            role=req.role
        )
        db.add(target_membership)
        db.flush()

        log_audit_event(
            db=db,
            organization_id=membership.organization_id,
            user_id=current_user.id,
            event_type="ROLE_ASSIGNED",
            entity_type="membership",
            entity_id=target_membership.id,
            summary=f"Assigned role '{req.role}' to {user.email}",
            details={"user_email": user.email, "role": req.role}
        )
    else:
        # User does not exist: provision new user transactionally
        if not req.full_name or len(req.full_name.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Full name is required when provisioning a new user (minimum 2 characters)."
            )

        if not req.password or len(req.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password is required when provisioning a new user (minimum 8 characters)."
            )

        hashed_pw = get_password_hash(req.password)
        new_user = User(
            email=clean_email,
            hashed_password=hashed_pw,
            full_name=req.full_name.strip(),
            is_active=True
        )
        db.add(new_user)
        db.flush()

        target_membership = OrganizationMembership(
            organization_id=membership.organization_id,
            user_id=new_user.id,
            role=req.role
        )
        db.add(target_membership)
        db.flush()

        log_audit_event(
            db=db,
            organization_id=membership.organization_id,
            user_id=current_user.id,
            event_type="MEMBER_PROVISIONED",
            entity_type="membership",
            entity_id=target_membership.id,
            summary=f"Provisioned new member '{new_user.full_name}' ({new_user.email}) with role '{req.role}'",
            details={"user_email": new_user.email, "role": req.role, "full_name": new_user.full_name}
        )
        user = new_user

    db.commit()
    db.refresh(target_membership)

    return MembershipOut(
        id=target_membership.id,
        organization_id=target_membership.organization_id,
        user_id=user.id,
        user_email=user.email,
        user_full_name=user.full_name,
        role=target_membership.role,
        created_at=target_membership.created_at
    )


# -----------------------------------------------------------------------------
# ROUND 3: TEAM INVITATIONS & DELIVERY FALLBACK ENGINE
# -----------------------------------------------------------------------------

@router.post("/{org_id}/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def invite_organization_member(
    org_id: str,
    req: InvitationCreate,
    membership: OrganizationMembership = Depends(require_org_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Invites a new or existing user to the workspace with role-based access.
    Enforces tenant isolation, token rotation, and zero-billing delivery fallback.
    """
    if org_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create invitations for a different organization."
        )

    try:
        invitation, raw_token, link = invitation_service.create_invitation(
            db=db,
            org_id=org_id,
            inviter_user=current_user,
            email=req.email,
            role=req.role,
            invitee_name=req.invitee_name
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ve))

    out = InvitationOut(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email_normalized,
        role=invitation.role,
        status=invitation.status,
        delivery_status=invitation.delivery_status,
        invited_by=invitation.invited_by,
        inviter_email_snapshot=invitation.inviter_email_snapshot,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        consumed_at=invitation.consumed_at,
        invitation_link=link
    )
    return out


@router.get("/{org_id}/invitations", response_model=List[InvitationOut])
def list_organization_invitations(
    org_id: str,
    membership: OrganizationMembership = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """
    Lists all pending, accepted, expired, or revoked invitations for the organization.
    """
    if org_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view invitations for a different organization."
        )

    invitations = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.organization_id == org_id
    ).order_by(OrganizationInvitation.created_at.desc()).all()

    return [
        InvitationOut(
            id=inv.id,
            organization_id=inv.organization_id,
            email=inv.email_normalized,
            role=inv.role,
            status=inv.status,
            delivery_status=inv.delivery_status,
            invited_by=inv.invited_by,
            inviter_email_snapshot=inv.inviter_email_snapshot,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
            consumed_at=inv.consumed_at,
            invitation_link=None
        )
        for inv in invitations
    ]


@router.post("/{org_id}/invitations/{invitation_id}/resend", response_model=InvitationOut)
def resend_organization_invitation(
    org_id: str,
    invitation_id: str,
    membership: OrganizationMembership = Depends(require_org_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Rotates the token, resets expiry to 7 days, and attempts re-delivery.
    """
    if org_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resend invitations for a different organization."
        )

    try:
        invitation, raw_token, link = invitation_service.resend_invitation(
            db=db,
            org_id=org_id,
            invitation_id=invitation_id,
            inviter_user=current_user
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    return InvitationOut(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email_normalized,
        role=invitation.role,
        status=invitation.status,
        delivery_status=invitation.delivery_status,
        invited_by=invitation.invited_by,
        inviter_email_snapshot=invitation.inviter_email_snapshot,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        consumed_at=invitation.consumed_at,
        invitation_link=link
    )


@router.post("/{org_id}/invitations/{invitation_id}/revoke", response_model=InvitationOut)
def revoke_organization_invitation(
    org_id: str,
    invitation_id: str,
    membership: OrganizationMembership = Depends(require_org_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revokes an active invitation immediately, preventing future redemption.
    """
    if org_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke invitations for a different organization."
        )

    try:
        invitation = invitation_service.revoke_invitation(
            db=db,
            org_id=org_id,
            invitation_id=invitation_id,
            user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    return InvitationOut(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email_normalized,
        role=invitation.role,
        status=invitation.status,
        delivery_status=invitation.delivery_status,
        invited_by=invitation.invited_by,
        inviter_email_snapshot=invitation.inviter_email_snapshot,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        consumed_at=invitation.consumed_at,
        invitation_link=None
    )
