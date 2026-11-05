"""Network bandwidth usage and time-series telemetry models."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class TrafficMeasurement(Base, TimestampMixin):
    __tablename__ = "traffic_measurements"

    interface: Mapped[str] = mapped_column(String(32), default="enp1s0")
    download_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    upload_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    rx_bytes: Mapped[int] = mapped_column(Integer, default=0)
    tx_bytes: Mapped[int] = mapped_column(Integer, default=0)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

