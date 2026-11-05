"""Firewall and network access policy models."""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class NetworkPolicy(Base, TimestampMixin):
    __tablename__ = "network_policies"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="block")  # block, allow, throttle, isolate
    target_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    target_group: Mapped[str] = mapped_column(String(32), default="")
    action: Mapped[str] = mapped_column(String(32), default="drop")  # drop, accept, limit
    value: Mapped[str] = mapped_column(String(64), default="")  # e.g. speed limit in kbps or port
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=10)

