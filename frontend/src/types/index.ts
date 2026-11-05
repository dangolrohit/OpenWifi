export interface User {
  id: number;
  username: string;
  role: 'super_admin' | 'admin' | 'viewer';
  is_active: boolean;
  last_login?: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  csrfToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface Device {
  id?: number;
  mac: string;
  ip: string;
  hostname: string;
  nickname: string;
  vendor: string;
  group: 'family' | 'customer' | 'staff' | 'default';
  is_blocked: boolean;
  is_trusted: boolean;
  speed_limit_mbps: number;
  schedule_enabled: boolean;
  schedule_start: string;
  schedule_end: string;
  status: 'REACHABLE' | 'STALE' | 'DELAY' | string;
  rx_bytes: number;
  tx_bytes: number;
  first_seen?: string;
  last_seen?: string;
}

export interface HotspotPlan {
  id?: number;
  plan_id: string;
  name: string;
  type: 'click' | 'voucher' | 'account';
  duration_minutes: number;
  speed_limit_mbps: number;
  is_active: boolean;
  description: string;
}

export interface Voucher {
  id?: number;
  code: string;
  plan_id: string;
  is_used: boolean;
  used_by_ip?: string;
  used_at?: string;
  created_at?: string;
}

export interface GuestSession {
  id?: number;
  ip: string;
  mac: string;
  plan_id: string;
  voucher_code?: string;
  speed_limit_mbps: number;
  authorized_at: string;
  expires_at: string;
  is_active: boolean;
}

export interface BandwidthTelemetry {
  interface: string;
  download_mbps: number;
  upload_mbps: number;
  rx_bytes: number;
  tx_bytes: number;
  rx_packets: number;
  tx_packets: number;
  simulated?: boolean;
}

export interface WifiStatus {
  connected: boolean;
  interface: string;
  ssid: string;
  bssid: string;
  mode: string;
  frequency_mhz: number;
  channel: number;
  signal_percent: number;
  signal_dbm: number;
  security: string;
  ip?: string;
  gateway?: string;
  dns: string[];
  simulated?: boolean;
}

export interface WifiNetwork {
  ssid: string;
  bssid: string;
  channel: number;
  signal_percent: number;
  security: string;
  in_use: boolean;
  simulated?: boolean;
}

export interface SystemHealth {
  cpu_percent: number;
  memory: {
    total_mb: number;
    used_mb: number;
    available_mb: number;
    percent: number;
  };
  disk: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent: number;
  };
  uptime_seconds: number;
  services: Record<string, { status: string; enabled: boolean }>;
  simulated?: boolean;
}

export interface AuditLogItem {
  id: number;
  event_type: string;
  actor: string;
  ip_address: string;
  description: string;
  severity: string;
  recorded_at: string;
}

export interface DnsQuery {
  timestamp: string;
  client: string;
  domain: string;
  type: string;
  simulated?: boolean;
}

export interface NetworkInterface {
  name: string;
  type: string;
  role: string;
  state: string;
  ip?: string;
  prefix?: number;
  mac?: string;
  mtu?: number;
  simulated?: boolean;
}

export interface NetworkRoute {
  destination: string;
  gateway: string;
  interface: string;
  metric?: number;
  protocol?: string;
  simulated?: boolean;
}
