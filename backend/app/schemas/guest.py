"""Hotspot plans, vouchers, and guest management schemas."""
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

class PlanSchema(BaseModel):
    id: Optional[int] = None
    plan_id: str
    name: str
    type: str = "voucher"
    duration_minutes: int
    speed_limit_mbps: int = 2
    is_active: bool = True
    description: str = ""

    class Config:
        from_attributes = True

class VoucherCreateRequest(BaseModel):
    plan_id: str = "standard"
    code: Optional[str] = Field(default=None, pattern=r"^[0-9]{6}$")

class VoucherResponse(BaseModel):
    id: Optional[int] = None
    code: str
    plan_id: str
    is_used: bool = False
    used_by_ip: Optional[str] = None
    used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GuestSessionResponse(BaseModel):
    id: Optional[int] = None
    ip: str
    mac: str = ""
    plan_id: str
    voucher_code: Optional[str] = None
    speed_limit_mbps: int = 2
    authorized_at: datetime
    expires_at: datetime
    is_active: bool = True

    @field_validator("authorized_at", "expires_at")
    @classmethod
    def ensure_utc(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    class Config:
        from_attributes = True

class GuestConnectRequest(BaseModel):
    plan_id: Optional[str] = None
    voucher: Optional[str] = Field(default=None, pattern=r"^[0-9]{6}$")

