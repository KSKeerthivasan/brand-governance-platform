from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime

class AuditEventOut(BaseModel):
    id: str
    organization_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    event_type: str
    entity_type: str
    entity_id: str
    summary: str
    details: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True
