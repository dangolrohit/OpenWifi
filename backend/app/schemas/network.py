"""Network status and telemetry schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class InterfaceInfo(BaseModel):
    name: str
    type: str
    role: str
    state: str
    ip: Optional[str] = None
    prefix: Optional[int] = None
    mac: Optional[str] = None
    mtu: Optional[int] = None
    simulated: bool = False

class RouteInfo(BaseModel):
    destination: str
    gateway: str
    interface: str
    metric: Optional[int] = None
    protocol: Optional[str] = None
    simulated: bool = False

class WifiStatusResponse(BaseModel):
    connected: bool
    interface: str = "wlp2s0"
    ssid: str = ""
    bssid: str = ""
    mode: str = "Infra"
    frequency_mhz: int = 5000
    channel: int = 36
    signal_percent: int = 0
    signal_dbm: int = -100
    security: str = ""
    ip: Optional[str] = None
    gateway: Optional[str] = None
    dns: List[str] = []
    simulated: bool = False

class WifiNetworkInfo(BaseModel):
    ssid: str
    bssid: str
    channel: int
    signal_percent: int
    security: str
    in_use: bool = False
    simulated: bool = False

class BandwidthTelemetry(BaseModel):
    interface: str
    download_mbps: float
    upload_mbps: float
    rx_bytes: int
    tx_bytes: int
    rx_packets: int
    tx_packets: int
    simulated: bool = False

class SystemHealthInfo(BaseModel):
    cpu_percent: float
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    uptime_seconds: int
    services: Dict[str, Any]
    simulated: bool = False

class AuditLogItem(BaseModel):
    id: int
    event_type: str
    actor: str
    ip_address: str
    description: str
    severity: str
    recorded_at: datetime

    class Config:
        from_attributes = True

