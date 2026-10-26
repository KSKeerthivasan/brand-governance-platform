from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import Organization, OrganizationMembership, User, OrganizationRole
from app.schemas.organization import OrganizationOut, MembershipOut, MembershipCreate
from app.api.deps import get_current_user, require_org_admin, require_any_member
from app.services.audit import log_audit_event

router = APIRouter()

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

@router.post("/members", response_model=MembershipOut)
def add_org_member(
    req: MembershipCreate,
    membership: OrganizationMembership = Depends(require_org_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.role not in OrganizationRole.ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{req.role}'. Valid roles: {', '.join(OrganizationRole.ALL_ROLES)}"
        )

    user = db.query(User).filter(User.email == req.user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{req.user_email}' not found."
        )

    existing = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == membership.organization_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if existing:
        existing.role = req.role
        db.commit()
        db.refresh(existing)
        target_membership = existing
    else:
        new_m = OrganizationMembership(
            organization_id=membership.organization_id,
            user_id=user.id,
            role=req.role
        )
        db.add(new_m)
        db.commit()
        db.refresh(new_m)
        target_membership = new_m

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

    return MembershipOut(
        id=target_membership.id,
        organization_id=target_membership.organization_id,
        user_id=user.id,
        user_email=user.email,
        user_full_name=user.full_name,
        role=target_membership.role,
        created_at=target_membership.created_at
    )
