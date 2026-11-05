"""System configuration and persistence model."""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(String(256), default="")

