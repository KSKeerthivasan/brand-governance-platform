import argparse
import secrets
import sys
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.organization import User, Organization, OrganizationMembership, OrganizationRole
from app.models.brand import Brand
from app.services.auth import get_password_hash

def provision_admin(
    org_name: str,
    org_slug: str,
    admin_email: str,
    admin_name: str,
    admin_password: str = None,
    brand_name: str = None,
    db: Session = None
) -> dict:
    """
    Safely provisions an initial organization and its administrator without hardcoded passwords.
    Returns details including generated password if one was auto-generated.
    """
    clean_email = admin_email.strip().lower()
    clean_slug = org_slug.strip().lower()
    brand_title = brand_name.strip() if brand_name else org_name.strip()

    generated_password = None
    if not admin_password:
        # Generate 24-character cryptographically secure password
        generated_password = secrets.token_urlsafe(18)
        plain_password = generated_password
    else:
        plain_password = admin_password

    if len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # 1. Organization lookup or creation
        org = db.query(Organization).filter(Organization.slug == clean_slug).first()
        if not org:
            org = Organization(
                id=str(uuid.uuid4()),
                name=org_name.strip(),
                slug=clean_slug
            )
            db.add(org)
            db.flush()

        # 2. User lookup or creation
        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=clean_email,
                full_name=admin_name.strip(),
                hashed_password=get_password_hash(plain_password),
                is_active=True
            )
            db.add(user)
            db.flush()
        else:
            # Update password if explicitly provided
            if admin_password:
                user.hashed_password = get_password_hash(admin_password)
            user.is_active = True
            db.flush()

        # 3. Membership
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == user.id
        ).first()

        if not membership:
            membership = OrganizationMembership(
                id=str(uuid.uuid4()),
                organization_id=org.id,
                user_id=user.id,
                role=OrganizationRole.ORG_ADMIN
            )
            db.add(membership)
            db.flush()
        else:
            membership.role = OrganizationRole.ORG_ADMIN
            db.flush()

        # 4. Brand
        brand = db.query(Brand).filter(Brand.organization_id == org.id).first()
        if not brand:
            brand = Brand(
                id=str(uuid.uuid4()),
                organization_id=org.id,
                name=brand_title,
                description=f"Primary brand workspace for {org_name.strip()}."
            )
            db.add(brand)
            db.flush()

        db.commit()

        return {
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_slug": org.slug,
            "user_id": user.id,
            "admin_email": user.email,
            "admin_name": user.full_name,
            "role": membership.role,
            "brand_name": brand.name,
            "password": plain_password,
            "was_generated": bool(generated_password)
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="Provision an organization and initial administrator.")
    parser.add_argument("--org-name", required=True, help="Display name of the organization")
    parser.add_argument("--org-slug", required=True, help="Unique URL slug of the organization")
    parser.add_argument("--admin-email", required=True, help="Email address of the administrator")
    parser.add_argument("--admin-name", required=True, help="Full name of the administrator")
    parser.add_argument("--password", required=False, default=None, help="Optional admin password (if omitted, high-entropy password is generated)")
    parser.add_argument("--brand-name", required=False, default=None, help="Initial brand name (defaults to org name)")

    args = parser.parse_args()

    try:
        result = provision_admin(
            org_name=args.org_name,
            org_slug=args.org_slug,
            admin_email=args.admin_email,
            admin_name=args.admin_name,
            admin_password=args.password,
            brand_name=args.brand_name
        )
        print("=" * 60)
        print("  ORGANIZATION & ADMINISTRATOR PROVISIONED SUCCESSFULLY")
        print("=" * 60)
        print(f"Organization: {result['organization_name']} (Slug: {result['organization_slug']})")
        print(f"Admin User:   {result['admin_name']} <{result['admin_email']}>")
        print(f"Assigned Role:{result['role']}")
        print(f"Primary Brand:{result['brand_name']}")
        if result['was_generated']:
            print("-" * 60)
            print(f"GENERATED SECURE PASSWORD: {result['password']}")
            print("Store this credential securely. It will not be shown again.")
        print("=" * 60)
    except Exception as exc:
        print(f"ERROR: Failed to provision administrator: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
