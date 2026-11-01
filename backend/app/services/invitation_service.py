import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from sqlalchemy.orm import Session
from app.config import settings
from app.models.organization import (
    Organization, User, OrganizationMembership, OrganizationInvitation, OrganizationRole
)
from app.schemas.organization import InvitationOut, InvitationVerifyOut
from app.services.auth import get_password_hash, verify_password
from app.services.audit import log_audit_event
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

class InvitationService:
    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def build_invitation_url(raw_token: str) -> str:
        """
        Builds the authoritative invitation URL using configured trusted frontend base URL.
        Never relies on unvalidated request host headers.
        """
        base = settings.frontend_base_url
        return f"{base}/accept-invitation?token={raw_token}"

    def create_invitation(
        self,
        db: Session,
        org_id: str,
        inviter_user: User,
        email: str,
        role: str,
        invitee_name: Optional[str] = None
    ) -> Tuple[OrganizationInvitation, str, str]:
        """
        Creates or rotates a cryptographically secure workspace invitation.
        Strictly enforces tenant isolation, email normalization, and zero-billing fallback delivery.
        Dispatches email via Gmail SMTP when configured, otherwise gracefully records fallback.
        """
        clean_email = email.strip().lower()

        # 1. Check if user is already a member
        existing_user = db.query(User).filter(User.email == clean_email).first()
        if existing_user:
            existing_m = db.query(OrganizationMembership).filter(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.user_id == existing_user.id
            ).first()
            if existing_m:
                raise ValueError(f"User with email '{clean_email}' is already a member of this organization ({existing_m.role}).")

        # 2. Check for existing pending invitation
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        expiry = datetime.utcnow() + timedelta(days=settings.INVITATION_EXPIRY_DAYS)
        invitation_link = self.build_invitation_url(raw_token)

        # 3. Resolve organization name for branded invitation email
        org = db.query(Organization).filter(Organization.id == org_id).first()
        org_name = org.name if org else "Workspace"

        # 4. Attempt email delivery via Gmail SMTP
        _sent, delivery_status, _msg = email_service.send_invitation_email(
            recipient_email=clean_email,
            role=role,
            organization_name=org_name,
            invitation_url=invitation_link,
            inviter_name=inviter_user.full_name,
            inviter_email=inviter_user.email,
            expiry_days=settings.INVITATION_EXPIRY_DAYS
        )
        delivery_method = "smtp_gmail" if email_service.is_configured else "unconfigured_demo_fallback"

        pending_inv = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.email_normalized == clean_email,
            OrganizationInvitation.status == "pending"
        ).first()

        if pending_inv:
            # Token rotation
            pending_inv.token_hash = token_hash
            pending_inv.role = role
            pending_inv.invited_by = inviter_user.id
            pending_inv.inviter_email_snapshot = inviter_user.email
            pending_inv.expires_at = expiry
            pending_inv.delivery_method = delivery_method
            pending_inv.delivery_status = delivery_status
            db.commit()
            db.refresh(pending_inv)
            invitation = pending_inv
            action = "INVITATION_ROTATED"
        else:
            invitation = OrganizationInvitation(
                organization_id=org_id,
                email_normalized=clean_email,
                role=role,
                token_hash=token_hash,
                delivery_method=delivery_method,
                delivery_status=delivery_status,
                status="pending",
                invited_by=inviter_user.id,
                inviter_email_snapshot=inviter_user.email,
                expires_at=expiry
            )
            db.add(invitation)
            db.commit()
            db.refresh(invitation)
            action = "INVITATION_CREATED"

        log_audit_event(
            db=db,
            organization_id=org_id,
            user_id=inviter_user.id,
            event_type=action,
            entity_type="organization_invitation",
            entity_id=invitation.id,
            summary=f"{action}: Invited {clean_email} as {role} (delivery: {delivery_status})",
            details={
                "email": clean_email,
                "role": role,
                "delivery_method": delivery_method,
                "delivery_status": delivery_status,
                "expires_at": expiry.isoformat()
            }
        )

        return invitation, raw_token, invitation_link

    def resend_invitation(
        self,
        db: Session,
        org_id: str,
        invitation_id: str,
        inviter_user: User
    ) -> Tuple[OrganizationInvitation, str, str]:
        """
        Rotates invitation token, refreshes expiration date, and attempts re-delivery.
        """
        invitation = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.id == invitation_id
        ).first()

        if not invitation:
            raise ValueError("Invitation not found.")

        if invitation.status == "accepted":
            raise ValueError("Cannot resend an invitation that has already been accepted.")

        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        expiry = datetime.utcnow() + timedelta(days=settings.INVITATION_EXPIRY_DAYS)
        invitation_link = self.build_invitation_url(raw_token)

        # Resolve org name for branded email
        org = db.query(Organization).filter(Organization.id == org_id).first()
        org_name = org.name if org else "Workspace"

        # Attempt re-delivery via Gmail SMTP
        _sent, delivery_status, _msg = email_service.send_invitation_email(
            recipient_email=invitation.email_normalized,
            role=invitation.role,
            organization_name=org_name,
            invitation_url=invitation_link,
            inviter_name=inviter_user.full_name,
            inviter_email=inviter_user.email,
            expiry_days=settings.INVITATION_EXPIRY_DAYS
        )
        delivery_method = "smtp_gmail" if email_service.is_configured else "unconfigured_demo_fallback"

        invitation.token_hash = token_hash
        invitation.status = "pending"
        invitation.expires_at = expiry
        invitation.invited_by = inviter_user.id
        invitation.inviter_email_snapshot = inviter_user.email
        invitation.delivery_method = delivery_method
        invitation.delivery_status = delivery_status

        db.commit()
        db.refresh(invitation)

        log_audit_event(
            db=db,
            organization_id=org_id,
            user_id=inviter_user.id,
            event_type="INVITATION_RESENT",
            entity_type="organization_invitation",
            entity_id=invitation.id,
            summary=f"Resent invitation to {invitation.email_normalized} with rotated token (delivery: {delivery_status})",
            details={
                "email": invitation.email_normalized,
                "role": invitation.role,
                "delivery_method": delivery_method,
                "delivery_status": delivery_status,
                "expires_at": expiry.isoformat()
            }
        )

        return invitation, raw_token, invitation_link

    def revoke_invitation(
        self,
        db: Session,
        org_id: str,
        invitation_id: str,
        user_id: str
    ) -> OrganizationInvitation:
        """
        Revokes a pending invitation immediately.
        """
        invitation = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.id == invitation_id
        ).first()

        if not invitation:
            raise ValueError("Invitation not found.")

        if invitation.status == "accepted":
            raise ValueError("Cannot revoke an already accepted invitation.")

        invitation.status = "revoked"
        db.commit()
        db.refresh(invitation)

        log_audit_event(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            event_type="INVITATION_REVOKED",
            entity_type="organization_invitation",
            entity_id=invitation.id,
            summary=f"Revoked invitation for {invitation.email_normalized}",
            details={"email": invitation.email_normalized, "role": invitation.role}
        )

        return invitation

    def verify_invitation_token(self, db: Session, raw_token: str) -> InvitationVerifyOut:
        """
        Public unauthenticated verification of an invitation token.
        Does not consume the token.
        """
        token_hash = self._hash_token(raw_token)
        invitation = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.token_hash == token_hash
        ).first()

        if not invitation:
            raise ValueError("Invalid invitation link or token.")

        if invitation.status == "revoked":
            raise ValueError("This invitation has been revoked by an administrator.")

        if invitation.status == "accepted":
            raise ValueError("This invitation has already been accepted.")

        if invitation.expires_at < datetime.utcnow():
            invitation.status = "expired"
            db.commit()
            raise ValueError("This invitation has expired. Please request a new invitation.")

        if invitation.status != "pending":
            raise ValueError(f"Invitation is no longer valid (status: {invitation.status}).")

        org = db.query(Organization).filter(Organization.id == invitation.organization_id).first()
        if not org or org.is_archived:
            raise ValueError("The organization associated with this invitation is inactive.")

        existing_user = db.query(User).filter(User.email == invitation.email_normalized).first()

        return InvitationVerifyOut(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            email=invitation.email_normalized,
            role=invitation.role,
            expires_at=invitation.expires_at,
            is_existing_user=existing_user is not None
        )

    def accept_invitation(
        self,
        db: Session,
        raw_token: str,
        full_name: Optional[str] = None,
        password: Optional[str] = None,
        authenticated_user: Optional[User] = None
    ) -> Tuple[User, Organization, str]:
        """
        Atomically consumes an invitation, provisions/validates user account,
        and creates the OrganizationMembership.
        Returns (user, organization, role).
        """
        token_hash = self._hash_token(raw_token)
        invitation = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.token_hash == token_hash
        ).first()

        if not invitation:
            raise ValueError("Invalid invitation link or token.")

        if invitation.status == "revoked":
            raise ValueError("This invitation has been revoked.")

        if invitation.status == "accepted":
            raise ValueError("This invitation has already been accepted.")

        if invitation.expires_at < datetime.utcnow():
            invitation.status = "expired"
            db.commit()
            raise ValueError("This invitation has expired.")

        if invitation.status != "pending":
            raise ValueError("Invitation is no longer pending.")

        org = db.query(Organization).filter(Organization.id == invitation.organization_id).first()
        if not org or org.is_archived:
            raise ValueError("The organization is inactive.")

        # Resolve User
        if authenticated_user:
            if authenticated_user.email.lower() != invitation.email_normalized.lower():
                raise ValueError(
                    f"Logged-in user email ({authenticated_user.email}) does not match invitation email ({invitation.email_normalized})."
                )
            target_user = authenticated_user
        else:
            existing_user = db.query(User).filter(User.email == invitation.email_normalized).first()
            if existing_user:
                if password and not verify_password(password, existing_user.hashed_password):
                    raise ValueError("Incorrect password for existing account.")
                target_user = existing_user
            else:
                if not full_name or len(full_name.strip()) < 2:
                    raise ValueError("Full name is required (minimum 2 characters).")
                if not password or len(password) < 8:
                    raise ValueError("Password is required (minimum 8 characters).")

                target_user = User(
                    email=invitation.email_normalized,
                    full_name=full_name.strip(),
                    hashed_password=get_password_hash(password),
                    is_active=True
                )
                db.add(target_user)
                db.flush()

        # Create or update membership
        existing_m = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == target_user.id
        ).first()

        if not existing_m:
            membership = OrganizationMembership(
                organization_id=org.id,
                user_id=target_user.id,
                role=invitation.role
            )
            db.add(membership)
            db.flush()
        else:
            existing_m.role = invitation.role

        # Consume invitation atomically
        invitation.status = "accepted"
        invitation.consumed_at = datetime.utcnow()
        invitation.accepted_by_user_id = target_user.id

        log_audit_event(
            db=db,
            organization_id=org.id,
            user_id=target_user.id,
            event_type="INVITATION_ACCEPTED",
            entity_type="organization_membership",
            entity_id=target_user.id,
            summary=f"User {target_user.email} accepted invitation and joined as {invitation.role}",
            details={
                "email": target_user.email,
                "role": invitation.role,
                "invitation_id": invitation.id
            }
        )

        db.commit()
        db.refresh(target_user)
        db.refresh(org)

        return target_user, org, invitation.role

invitation_service = InvitationService()
