from typing import Generator, Optional, List
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import User, OrganizationMembership, OrganizationRole
from app.services.auth import decode_access_token, is_token_revoked

security = HTTPBearer(auto_error=False)

def get_current_user(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not auth_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token."
        )

    token = auth_credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token."
        )

    # Enforce server-side token revocation check (Milestone 5E)
    jti = payload.get("jti")
    if jti and is_token_revoked(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked or invalidated. Please log in again."
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or disabled."
        )

    return user


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
        auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> OrganizationMembership:
        """
        Derives caller's organization membership and role strictly from persisted records.
        Client-controlled headers like X-User-Role or X-User-Id are NEVER inspected.
        If X-Organization-Id is provided, validates that the user actually belongs to that organization.
        If omitted, resolves using the active organization ID embedded in the verified JWT token.
        """
        target_org_id = x_organization_id
        if not target_org_id and auth_credentials:
            token = auth_credentials.credentials
            payload = decode_access_token(token) or {}
            target_org_id = payload.get("org_id")

        query = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == current_user.id
        )
        if target_org_id:
            query = query.filter(OrganizationMembership.organization_id == target_org_id)

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
