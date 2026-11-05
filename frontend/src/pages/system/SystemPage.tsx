import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Cpu, HardDrive, Server, ShieldCheck, Clock } from 'lucide-react';
import { api } from '@/services/api';
import { Badge } from '@/elements/badges/Badge';
import { StatusCard } from '@/components/common/StatusCard';
import { formatUptime } from '@/utils/formatters';

export const SystemPage: React.FC = () => {
  const { data: health, isLoading } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: api.system.getHealth,
    refetchInterval: 3000,
  });

  const cpu = health?.cpu_percent || 0;
  const mem = health?.memory || { total_mb: 0, used_mb: 0, percent: 0 };
  const disk = health?.disk || { total_gb: 0, used_gb: 0, percent: 0 };
  const services = health?.services || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          System Monitoring & Health
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Real-time resource supervisor and critical host service status.
        </p>
      </div>

      {/* Top Resource Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatusCard
          title="CPU Load"
          value={`${cpu}%`}
          subtitle="Processor Utilization"
          icon={Cpu}
        />
        <StatusCard
          title="Memory (RAM)"
          value={`${mem.percent}%`}
          subtitle={`${mem.used_mb} MB / ${mem.total_mb} MB`}
          icon={Activity}
          iconColor="text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60"
        />
        <StatusCard
          title="Root Storage"
          value={`${disk.percent}%`}
          subtitle={`${disk.used_gb} GB / ${disk.total_gb} GB`}
          icon={HardDrive}
          iconColor="text-purple-600 bg-purple-50 dark:bg-purple-950/60"
        />
        <StatusCard
          title="System Uptime"
          value={formatUptime(health?.uptime_seconds || 0)}
          subtitle="Host operational time"
          icon={Clock}
          iconColor="text-sky-600 bg-sky-50 dark:bg-sky-950/60"
        />
      </div>

      {/* Tracked Services Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Server className="w-4 h-4 text-brand-600" /> Host Service Supervisor
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3">Service Name</th>
                <th className="px-6 py-3">Component Role</th>
                <th className="px-6 py-3">Auto-Start</th>
                <th className="px-6 py-3 text-right">Runtime Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {Object.entries(services).map(([name, sInfo]: [string, any]) => (
                <tr key={name}>
                  <td className="px-6 py-3.5 font-mono font-bold text-slate-900 dark:text-slate-100">
                    {name}.service
                  </td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">
                    {name === 'NetworkManager'
                      ? 'Host Networking Daemon'
                      : name === 'docker'
                      ? 'Container Runtime'
                      : name === 'cloudflared'
                      ? 'Cloudflare Zero Trust Tunnel'
                      : name === 'postgresql'
                      ? 'Database Server'
                      : name === 'wifirouter_agent' || name === 'wifirouter-agent'
                      ? 'Privileged Linux Network Agent'
                      : 'FastAPI Backend'}
                  </td>
                  <td className="px-6 py-3.5 text-xs font-semibold text-emerald-600">
                    Enabled
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <Badge variant={sInfo.status === 'active' ? 'success' : 'danger'}>
                      {sInfo.status.toUpperCase()}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

