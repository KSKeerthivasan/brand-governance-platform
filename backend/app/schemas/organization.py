from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class OrganizationBase(BaseModel):
    name: str
    slug: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationOut(OrganizationBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MembershipCreate(BaseModel):
    user_email: str
    role: str

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
