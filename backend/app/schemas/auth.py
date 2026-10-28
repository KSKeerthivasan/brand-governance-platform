from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    organization_id: Optional[str] = None
    organization_slug: Optional[str] = None

class SwitchOrgRequest(BaseModel):
    organization_id: Optional[str] = None
    organization_slug: Optional[str] = None

class DevLoginRequest(BaseModel):
    role: str  # org_admin, knowledge_reviewer, content_creator, approval_manager
    organization_slug: Optional[str] = "freshsip"

class UserOut(UserBase):
    id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    is_demo: bool = False

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[str] = None
    is_demo: Optional[bool] = None
