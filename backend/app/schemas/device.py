"""Device management schemas."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ScheduleSchema(BaseModel):
    enabled: bool = False
    start: str = "22:00"
    end: str = "06:00"

class DeviceUpdateRequest(BaseModel):
    ip: str
    nickname: Optional[str] = Field(None, max_length=128)
    group: Optional[str] = Field(None, pattern="^(family|customer|staff|default)$")
    speed_limit_mbps: Optional[int] = Field(None, ge=0, le=10000)
    is_trusted: Optional[bool] = None
    schedule: Optional[ScheduleSchema] = None

class DeviceBlockRequest(BaseModel):
    ip: str
    blocked: bool = True

class DeviceResponse(BaseModel):
    id: Optional[int] = None
    mac: str
    ip: str
    hostname: str = ""
    nickname: str = ""
    vendor: str = ""
    group: str = "default"
    is_blocked: bool = False
    is_trusted: bool = False
    speed_limit_mbps: int = 0
    schedule_enabled: bool = False
    schedule_start: str = "22:00"
    schedule_end: str = "06:00"
    status: str = "REACHABLE"
    rx_bytes: int = 0
    tx_bytes: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True

