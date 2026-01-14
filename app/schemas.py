from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional, List, Any
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    username: Optional[str] = None
    profile_pic: Optional[str] = None

class UserInfo(UserBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class AuthToken(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo

class GoogleAuth(BaseModel):
    id_token: Optional[str] = None
    access_token: Optional[str] = None

class URLBase(BaseModel):
    long_url: HttpUrl
    custom_slug: Optional[str] = None
    max_clicks: Optional[int] = None
    expires_in: Optional[int] = None # in seconds
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_cloaked: Optional[bool] = False

class URLCreate(URLBase):
    pass

class URLUpdate(BaseModel):
    long_url: Optional[HttpUrl] = None
    custom_slug: Optional[str] = None
    max_clicks: Optional[int] = None
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_cloaked: Optional[bool] = None

class URLInfo(BaseModel):
    id: int
    long_url: str
    slug: str
    clicks: int
    max_clicks: Optional[int]
    expires_at: Optional[datetime]
    has_password: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_cloaked: bool = False
    created_at: datetime
    user_id: Optional[int] = None

    class Config:
        from_attributes = True

class BundleItem(BaseModel):
    label: str
    url: str
    is_spotlight: Optional[bool] = False

class BundleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    items: List[BundleItem]
    theme_color: Optional[str] = "#00f2ff"
    bg_color: Optional[str] = "#0a0a0a"
    text_color: Optional[str] = "#888888"
    title_color: Optional[str] = "#ffffff"
    card_color: Optional[str] = "rgba(255,255,255,0.05)"
    bg_image: Optional[str] = None
    profile_image: Optional[str] = None
    custom_slug: Optional[str] = None
    max_clicks: Optional[int] = None
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_cloaked: Optional[bool] = False
    access_level: Optional[str] = "restricted"

class BundleUpdate(BaseModel):
    custom_slug: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    items: Optional[List[BundleItem]] = None
    theme_color: Optional[str] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    title_color: Optional[str] = None
    card_color: Optional[str] = None
    bg_image: Optional[str] = None
    profile_image: Optional[str] = None
    max_clicks: Optional[int] = None
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_cloaked: Optional[bool] = None
    access_level: Optional[str] = None

class BundleInfo(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str]
    items: List[dict]
    theme_color: str
    bg_color: str
    text_color: str
    title_color: str
    card_color: str
    bg_image: Optional[str] = None
    profile_image: Optional[str] = None
    clicks: int
    max_clicks: Optional[int]
    expires_at: Optional[datetime]
    has_password: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    is_cloaked: bool = False
    access_level: str = "restricted"
    manager_token: Optional[str] = None
    analyst_token: Optional[str] = None
    created_at: datetime
    user_id: Optional[int] = None

    class Config:
        from_attributes = True

class ClickStats(BaseModel):
    timestamp: datetime
    referer: Optional[str]
    device_type: Optional[str]

class AnalyticsReport(BaseModel):
    total_clicks: int
    clicks_over_time: List[dict] # {date: str, count: int}
    device_stats: List[dict] # {device: str, count: int}
    top_referers: List[dict] # {referer: str, count: int}

class CollaborationCreate(BaseModel):
    collaborator_email: EmailStr
    bundle_id: Optional[int] = None # Optional for account-wide, but we'll use it for per-studio
    role: str = "manager"

class CollaborationInfo(BaseModel):
    id: int
    owner_id: int
    collaborator_id: int
    bundle_id: Optional[int]
    collaborator_name: Optional[str]
    collaborator_username: Optional[str]
    collaborator_pic: Optional[str]
    bundle_title: Optional[str] = None
    role: str
    created_at: datetime
    class Config:
        from_attributes = True

class NotificationInfo(BaseModel):
    id: int
    type: str
    title: str
    message: str
    is_read: bool
    link: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True
