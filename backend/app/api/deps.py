from typing import Generator, Optional, List
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import User, OrganizationMembership, OrganizationRole
from app.services.auth import decode_access_token

security = HTTPBearer(auto_error=False)

def get_current_user(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not auth_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token."
        )

    token = auth_credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token."
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive."
        )
    return user


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> OrganizationMembership:
        # Check membership in the specified organization
        query = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == current_user.id
        )
        if x_organization_id:
            query = query.filter(OrganizationMembership.organization_id == x_organization_id)

        membership = query.first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant Isolation: You are not a member of the requested organization."
            )

        if self.allowed_roles and membership.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission Denied: Action requires one of roles: {', '.join(self.allowed_roles)}. Your role is '{membership.role}'."
            )

        return membership

# Convenience role checkers
require_any_member = RoleChecker(OrganizationRole.ALL_ROLES)
require_org_admin = RoleChecker([OrganizationRole.ORG_ADMIN])
require_knowledge_reviewer = RoleChecker([OrganizationRole.KNOWLEDGE_REVIEWER, OrganizationRole.ORG_ADMIN])
require_content_creator = RoleChecker([OrganizationRole.CONTENT_CREATOR, OrganizationRole.ORG_ADMIN])
require_approval_manager = RoleChecker([OrganizationRole.APPROVAL_MANAGER])
