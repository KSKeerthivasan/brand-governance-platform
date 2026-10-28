from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ContentVersionOut(BaseModel):
    id: str
    content_item_id: str
    version_num: int
    body_text: str
    checksum: str
    created_by: Optional[str] = None
    created_at: datetime
    poster_file_path: Optional[str] = None
    poster_asset_id: Optional[str] = None
    poster_alt_text: Optional[str] = None
    poster_url: Optional[str] = None
    is_pdf: bool = False
    page_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class ContentItemCreate(BaseModel):
    brand_id: str
    title: str
    channel: str = "Social Media"
    body_text: str
    poster_file_path: Optional[str] = None
    poster_asset_id: Optional[str] = None
    poster_alt_text: Optional[str] = None

class ContentItemUpdate(BaseModel):
    title: Optional[str] = None
    channel: Optional[str] = None
    body_text: str
    poster_file_path: Optional[str] = None
    poster_asset_id: Optional[str] = None
    poster_alt_text: Optional[str] = None

class ContentItemOut(BaseModel):
    id: str
    organization_id: str
    brand_id: str
    created_by: str
    title: str
    channel: str
    current_version_num: int
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[ContentVersionOut] = None

    model_config = ConfigDict(from_attributes=True)
