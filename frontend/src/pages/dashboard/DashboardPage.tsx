import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Smartphone,
  ArrowDown,
  ArrowUp,
  Wifi,
  ShieldAlert,
  Users,
  Activity,
  Cpu,
  HardDrive,
} from 'lucide-react';
import { StatusCard } from '@/components/common/StatusCard';
import { BandwidthAreaChart } from '@/components/charts/BandwidthAreaChart';
import { api } from '@/services/api';
import { formatBytes, formatMbps, formatUptime } from '@/utils/formatters';

export const DashboardPage: React.FC = () => {
  const { data: summary, isLoading } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: api.dashboard.getSummary,
    refetchInterval: 3000,
  });

  const { data: traffic } = useQuery({
    queryKey: ['trafficHistory', 24],
    queryFn: () => api.analytics.getTraffic(24),
    refetchInterval: 10000,
  });

  if (isLoading && !summary) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  const bw = summary?.bandwidth || {};
  const wifi = summary?.wifi || {};
  const dev = summary?.devices || {};
  const health = summary?.health || {};

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Network Dashboard
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Live overview of gateway throughput, connected devices, and active access rules.
        </p>
      </div>

      {/* Top Telemetry Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="Active Devices"
          value={dev.total || 0}
          subtitle={`${dev.family || 0} Family · ${dev.customer || 0} Customer`}
          icon={Smartphone}
        />
        <StatusCard
          title="Live Download"
          value={formatMbps(bw.download_mbps || 0)}
          subtitle={`RX Total: ${formatBytes(bw.rx_bytes || 0)}`}
          icon={ArrowDown}
          iconColor="text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60"
        />
        <StatusCard
          title="Live Upload"
          value={formatMbps(bw.upload_mbps || 0)}
          subtitle={`TX Total: ${formatBytes(bw.tx_bytes || 0)}`}
          icon={ArrowUp}
          iconColor="text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/60"
        />
        <StatusCard
          title="Active Hotspot Guests"
          value={dev.active_guests || 0}
          subtitle={`${dev.blocked || 0} addresses blocked`}
          icon={Users}
          iconColor="text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/60"
        />
      </div>

      {/* Chart Section */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Bandwidth Telemetry (24h)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Downstream interface throughput (enp1s0)
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Download
            </span>
            <span className="flex items-center gap-1.5 text-sky-600 dark:text-sky-400">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500" /> Upload
            </span>
          </div>
        </div>
        <BandwidthAreaChart data={traffic?.history || []} />
      </div>

      {/* Bottom Status Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Wi-Fi & Gateway Connection Info */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Wifi className="w-4 h-4 text-brand-600" /> Upstream Wi-Fi
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              {wifi.connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">SSID</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">{wifi.ssid || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">Signal Quality</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">{wifi.signal_percent || 0}% ({wifi.signal_dbm || -100} dBm)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">IP / Gateway</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">{wifi.ip || '192.168.1.100'} → {wifi.gateway || '192.168.1.1'}</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-500">Security / Channel</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">{wifi.security || 'WPA2'} · CH {wifi.channel || 36}</span>
            </div>
          </div>
        </div>

        {/* System Resource Health */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-600" /> Host System Health
            </h3>
            <span className="text-xs text-slate-500">Uptime: {formatUptime(health.uptime_seconds || 0)}</span>
          </div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                  <Cpu className="w-3.5 h-3.5" /> CPU Utilization
                </span>
                <span>{health.cpu_percent || 0}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-brand-500 rounded-full transition-all"
                  style={{ width: `${Math.min(100, health.cpu_percent || 0)}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                  <Activity className="w-3.5 h-3.5" /> RAM Utilization
                </span>
                <span>{health.memory?.percent || 0}% ({health.memory?.used_mb || 0} MB / {health.memory?.total_mb || 0} MB)</span>
              </div>
              <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all"
                  style={{ width: `${Math.min(100, health.memory?.percent || 0)}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                  <HardDrive className="w-3.5 h-3.5" /> Root Disk Storage
                </span>
                <span>{health.disk?.percent || 0}% ({health.disk?.used_gb || 0} GB / {health.disk?.total_gb || 0} GB)</span>
              </div>
              <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full transition-all"
                  style={{ width: `${Math.min(100, health.disk?.percent || 0)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

