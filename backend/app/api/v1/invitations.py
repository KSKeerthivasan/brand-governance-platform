import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import User
from app.schemas.organization import InvitationVerifyOut, InvitationAcceptIn
from app.schemas.auth import Token, UserOut
from app.services.invitation_service import invitation_service
from app.services.auth import create_access_token
from app.api.deps import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/verify", response_model=InvitationVerifyOut)
def verify_invitation_token(
    token: str = Query(..., description="Invitation secret token"),
    db: Session = Depends(get_db)
):
    """
    Public unauthenticated endpoint to verify invitation token validity
    and return workspace metadata before account creation or sign-in.
    """
    try:
        return invitation_service.verify_invitation_token(db=db, raw_token=token)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/accept", response_model=Token)
def accept_invitation(
    req: InvitationAcceptIn,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Consumes invitation token atomically inside a database transaction,
    provisions or validates the user account, assigns the role membership,
    and returns an authenticated application JWT.
    """
    try:
        user, org, role = invitation_service.accept_invitation(
            db=db,
            raw_token=req.token,
            full_name=req.full_name,
            password=req.password,
            authenticated_user=current_user
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    # Issue application JWT
    access_token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "org_id": org.id,
            "role": role,
            "is_demo": False
        }
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=role,
        is_demo=False
    )
