import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Gauge, ArrowDown, ArrowUp, Plus, ShieldCheck } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/elements/buttons/Button';
import { StatusCard } from '@/components/common/StatusCard';
import { formatMbps, formatBytes } from '@/utils/formatters';

export const BandwidthPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [targetIp, setTargetIp] = useState('');
  const [speedLimit, setSpeedLimit] = useState(5);

  const { data: telemetry } = useQuery({
    queryKey: ['liveBandwidth'],
    queryFn: api.bandwidth.getLive,
    refetchInterval: 3000,
  });

  const { data: fwStatus } = useQuery({
    queryKey: ['filteringStatus'],
    queryFn: api.filtering.getStatus,
  });

  const shapeMutation = useMutation({
    mutationFn: ({ ip, limit }: { ip: string; limit: number }) => api.bandwidth.shape(ip, limit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['filteringStatus'] });
      setTargetIp('');
    },
  });

  const speedLimits = fwStatus?.speed_limits || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Bandwidth Management & QoS
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Apply Linux Traffic Control (tc HTB/fq_codel) rate limits to prevent bandwidth monopolization.
        </p>
      </div>

      {/* Real-time Speeds Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatusCard
          title="Downstream Download Rate"
          value={formatMbps(telemetry?.download_mbps || 0)}
          subtitle={`Total Received: ${formatBytes(telemetry?.rx_bytes || 0)}`}
          icon={ArrowDown}
          iconColor="text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60"
        />
        <StatusCard
          title="Downstream Upload Rate"
          value={formatMbps(telemetry?.upload_mbps || 0)}
          subtitle={`Total Transmitted: ${formatBytes(telemetry?.tx_bytes || 0)}`}
          icon={ArrowUp}
          iconColor="text-sky-600 bg-sky-50 dark:bg-sky-950/60"
        />
      </div>

      {/* Apply QoS Form */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-3">
          Configure Bandwidth Throttle
        </h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (targetIp.trim()) {
              shapeMutation.mutate({ ip: targetIp.trim(), limit: speedLimit });
            }
          }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl"
        >
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Target IP Address
            </label>
            <input
              type="text"
              required
              placeholder="e.g. 192.168.16.105"
              value={targetIp}
              onChange={(e) => setTargetIp(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Speed Limit (Mbps)
            </label>
            <input
              type="number"
              min="1"
              max="1000"
              required
              value={speedLimit}
              onChange={(e) => setSpeedLimit(parseInt(e.target.value, 10) || 1)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" isLoading={shapeMutation.isPending} className="w-full">
              Apply QoS Policy
            </Button>
          </div>
        </form>
      </div>

      {/* Active Rules Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
            Active Rate-Limiting Policies
          </h3>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <tr>
              <th className="px-6 py-3">IP Address</th>
              <th className="px-6 py-3">Configured Limit</th>
              <th className="px-6 py-3">Burst Rate</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {Object.entries(speedLimits).map(([ip, limit]) => (
              <tr key={ip}>
                <td className="px-6 py-3.5 font-mono font-medium">{ip}</td>
                <td className="px-6 py-3.5 font-semibold text-brand-600 dark:text-brand-400">
                  {String(limit)} Mbps ({Number(limit) * 125} KB/s)
                </td>
                <td className="px-6 py-3.5 text-xs text-slate-500">
                  {Math.max(100, Math.floor(Number(limit) * 125 * 0.2))} KB burst
                </td>
                <td className="px-6 py-3.5 text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => shapeMutation.mutate({ ip, limit: 0 })}
                  >
                    Remove Limit
                  </Button>
                </td>
              </tr>
            ))}
            {Object.keys(speedLimits).length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-slate-400 text-xs">
                  No rate-limiting rules currently active.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
