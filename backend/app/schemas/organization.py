import re
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import datetime

class OrganizationBase(BaseModel):
    name: str
    slug: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationOnboard(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=255, description="Official company or organization name")
    organization_slug: str = Field(..., min_length=2, max_length=100, description="URL-friendly unique slug")
    brand_name: str = Field(..., min_length=2, max_length=255, description="Initial brand name")
    brand_description: Optional[str] = Field(None, max_length=1000, description="Brand description / positioning statement")
    admin_full_name: str = Field(..., min_length=2, max_length=255, description="Full name of initial Organization Administrator")
    admin_email: EmailStr = Field(..., description="Administrator email address")
    admin_password: str = Field(..., min_length=8, max_length=128, description="Secure account password")

    @field_validator("organization_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", clean):
            raise ValueError("Organization slug must contain only lowercase letters, numbers, and hyphens (e.g., 'veritas-tea').")
        return clean

class OrganizationOut(OrganizationBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MembershipCreate(BaseModel):
    user_email: EmailStr = Field(..., description="Corporate or member email address")
    role: str = Field(..., description="Assigned role: knowledge_reviewer, content_creator, approval_manager")
    full_name: Optional[str] = Field(None, min_length=2, max_length=255, description="Full name of the team member")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Initial secure account password")

class MembershipOut(BaseModel):
    id: str
    organization_id: str
    user_id: str
    user_email: str
    user_full_name: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BrandBase(BaseModel):
    name: str
    description: Optional[str] = None

class BrandCreate(BrandBase):
    pass

class BrandOut(BrandBase):
    id: str
    organization_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationCreate(BaseModel):
    email: EmailStr = Field(..., description="Corporate or member email address")
    role: str = Field(..., description="Assigned role: org_admin, knowledge_reviewer, content_creator, approval_manager")
    invitee_name: Optional[str] = Field(None, max_length=255, description="Display name of invitee")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        permitted = {"org_admin", "knowledge_reviewer", "content_creator", "approval_manager"}
        if v not in permitted:
            raise ValueError(f"Invalid role '{v}'. Permitted: {', '.join(permitted)}")
        return v


class InvitationOut(BaseModel):
    id: str
    organization_id: str
    email: str
    role: str
    status: str
    delivery_status: str
    invited_by: Optional[str] = None
    inviter_email_snapshot: str
    expires_at: datetime
    created_at: datetime
    consumed_at: Optional[datetime] = None
    invitation_link: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvitationVerifyOut(BaseModel):
    organization_id: str
    organization_name: str
    organization_slug: str
    email: str
    role: str
    expires_at: datetime
    is_existing_user: bool


class InvitationAcceptIn(BaseModel):
    token: str = Field(..., min_length=16, description="Invitation secret token")
    full_name: Optional[str] = Field(None, min_length=2, max_length=255, description="Full name if creating new account")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Password for account authentication")
