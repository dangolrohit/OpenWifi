import { apiClient, setCsrfToken } from './client';
import {
  User, Device, HotspotPlan, Voucher, GuestSession,
  BandwidthTelemetry, WifiStatus, WifiNetwork, SystemHealth,
  AuditLogItem, DnsQuery, DeviceActivityPage, NetworkInterface, NetworkRoute
} from '@/types';

export const api = {
  auth: {
    login: async (username: string, password: string) => {
      const res = await apiClient<{ ok: boolean; token: string; csrf_token: string; user: User }>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setCsrfToken(res.csrf_token);
      return res;
    },
    logout: async () => {
      const res = await apiClient<{ ok: boolean }>('/api/v1/auth/logout', { method: 'POST' });
      setCsrfToken(null);
      return res;
    },
    me: async () => {
      const res = await apiClient<{ ok: boolean; token: string; csrf_token: string; user: User }>('/api/v1/auth/me');
      setCsrfToken(res.csrf_token);
      return res;
    },
    changePassword: (current_password: string, new_password: string) =>
      apiClient<{ ok: boolean }>('/api/v1/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password, new_password }),
      }),
  },

  dashboard: {
    getSummary: () => apiClient<any>('/api/v1/dashboard/summary'),
  },

  wifi: {
    getStatus: () => apiClient<WifiStatus>('/api/v1/wifi/status'),
    scan: () => apiClient<{ networks: WifiNetwork[] }>('/api/v1/wifi/scan'),
  },

  devices: {
    list: () => apiClient<Device[]>('/api/v1/devices'),
    update: (ip: string, updates: Partial<Device> & { schedule?: any; assign_plan_id?: string; extend_minutes?: number; revoke_internet?: boolean }) =>
      apiClient<Device>(`/api/v1/devices/${ip}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      }),
    block: (ip: string, blocked: boolean) =>
      apiClient<Device>(`/api/v1/devices/${ip}/block`, {
        method: 'POST',
        body: JSON.stringify({ ip, blocked }),
      }),
    grantPlan: (ip: string, plan_id: string) =>
      apiClient<Device>(`/api/v1/devices/${ip}`, {
        method: 'PUT',
        body: JSON.stringify({ ip, assign_plan_id: plan_id }),
      }),
    extendTime: (ip: string, minutes: number = 30) =>
      apiClient<Device>(`/api/v1/devices/${ip}`, {
        method: 'PUT',
        body: JSON.stringify({ ip, extend_minutes: minutes }),
      }),
    revokeInternet: (ip: string) =>
      apiClient<Device>(`/api/v1/devices/${ip}`, {
        method: 'PUT',
        body: JSON.stringify({ ip, revoke_internet: true }),
      }),
  },

  filtering: {
    getStatus: () => apiClient<any>('/api/v1/filtering/status'),
    block: (ip: string) => apiClient<any>('/api/v1/filtering/block', { method: 'POST', body: JSON.stringify({ ip }) }),
    unblock: (ip: string) => apiClient<any>('/api/v1/filtering/unblock', { method: 'POST', body: JSON.stringify({ ip }) }),
  },

  bandwidth: {
    getLive: () => apiClient<BandwidthTelemetry>('/api/v1/bandwidth/live'),
    shape: (ip: string, speed_limit_mbps: number) =>
      apiClient<any>('/api/v1/bandwidth/shape', {
        method: 'POST',
        body: JSON.stringify({ ip, speed_limit_mbps }),
      }),
  },

  guests: {
    getPlans: () => apiClient<HotspotPlan[]>('/api/v1/guests/plans'),
    updatePlans: (plans: HotspotPlan[]) =>
      apiClient<HotspotPlan[]>('/api/v1/guests/plans', {
        method: 'PUT',
        body: JSON.stringify(plans),
      }),
    getVouchers: () => apiClient<Voucher[]>('/api/v1/guests/vouchers'),
    createVoucher: (plan_id: string, code?: string) =>
      apiClient<Voucher>('/api/v1/guests/vouchers', {
        method: 'POST',
        body: JSON.stringify({ plan_id, code }),
      }),
    deleteVoucher: (code: string) =>
      apiClient<{ ok: boolean }>(`/api/v1/guests/vouchers/${code}`, {
        method: 'DELETE',
      }),
    getSessions: () => apiClient<GuestSession[]>('/api/v1/guests/sessions'),
    extendSession: (ip: string, minutes: number = 30) =>
      apiClient<{ ok: boolean; session: GuestSession }>('/api/v1/guests/sessions/extend', {
        method: 'POST',
        body: JSON.stringify({ ip, minutes }),
      }),
    revokeSession: (ip: string) =>
      apiClient<{ ok: boolean }>('/api/v1/guests/sessions/revoke', {
        method: 'POST',
        body: JSON.stringify({ ip }),
      }),
  },

  analytics: {
    getTraffic: (hours: number = 24) =>
      apiClient<{ history: any[] }>(`/api/v1/analytics/traffic?hours=${hours}`),
  },

  logs: {
    getAuditLogs: (limit: number = 100) =>
      apiClient<AuditLogItem[]>(`/api/v1/logs/audit?limit=${limit}`),
    getDnsActivity: (client?: string) =>
      apiClient<{ queries: DnsQuery[] }>(`/api/v1/logs/dns${client ? `?client=${client}` : ''}`),
    getDeviceActivity: (client: string, page: number = 1) =>
      apiClient<DeviceActivityPage>(`/api/v1/logs/dns/device-activity?client=${encodeURIComponent(client)}&page=${page}`),
    clearDnsActivity: () =>
      apiClient<{ ok: boolean }>('/api/v1/logs/dns/clear', { method: 'POST' }),
  },

  network: {
    getInterfaces: () => apiClient<{ interfaces: NetworkInterface[] }>('/api/v1/network/interfaces'),
    getRoutes: () => apiClient<{ routes: NetworkRoute[]; default_gateway: any }>('/api/v1/network/routes'),
  },

  system: {
    getHealth: () => apiClient<SystemHealth>('/api/v1/system/health'),
  },

  settings: {
    getSettings: () => apiClient<any>('/api/v1/settings'),
    updateSettings: (settings: Record<string, any>) =>
      apiClient<{ ok: boolean }>('/api/v1/settings', {
        method: 'PUT',
        body: JSON.stringify(settings),
      }),
  },
};

