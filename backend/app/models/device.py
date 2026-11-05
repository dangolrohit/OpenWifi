"""Connected device model with groups, nicknames, QoS, and curfew schedules."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    mac: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    ip: Mapped[str] = mapped_column(String(45), index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(128), default="")
    nickname: Mapped[str] = mapped_column(String(128), default="")
    vendor: Mapped[str] = mapped_column(String(128), default="")
    group: Mapped[str] = mapped_column(String(32), default="default")  # family, customer, staff, default
    
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    speed_limit_mbps: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    
    # Bedtime / curfew schedules
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_start: Mapped[str] = mapped_column(String(8), default="22:00")
    schedule_end: Mapped[str] = mapped_column(String(8), default="06:00")

    # Telemetry
    rx_bytes: Mapped[int] = mapped_column(Integer, default=0)
    tx_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="REACHABLE")  # REACHABLE, STALE, DELAY
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

