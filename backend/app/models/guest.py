"""Hotspot plans, vouchers, and guest session models."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class HotspotPlan(Base, TimestampMixin):
    __tablename__ = "hotspot_plans"

    plan_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="voucher")  # click, voucher, account
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    speed_limit_mbps: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(256), default="")

class Voucher(Base, TimestampMixin):
    __tablename__ = "vouchers"

    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class GuestSession(Base, TimestampMixin):
    __tablename__ = "guest_sessions"

    ip: Mapped[str] = mapped_column(String(45), index=True, nullable=False)
    mac: Mapped[str] = mapped_column(String(32), default="")
    plan_id: Mapped[str] = mapped_column(String(32), default="starter")
    voucher_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    speed_limit_mbps: Mapped[int] = mapped_column(Integer, default=2)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class GuestAccount(Base, TimestampMixin):
    __tablename__ = "guest_accounts"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(32), default="standard")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    speed_limit_mbps: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

