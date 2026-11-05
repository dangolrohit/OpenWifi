import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, Download, ArrowDown, ArrowUp, Zap } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/elements/buttons/Button';
import { StatusCard } from '@/components/common/StatusCard';
import { BandwidthAreaChart } from '@/components/charts/BandwidthAreaChart';
import { formatMbps, formatBytes } from '@/utils/formatters';

export const AnalyticsPage: React.FC = () => {
  const [timeWindow, setTimeWindow] = useState<number>(24);

  const { data: traffic, isLoading } = useQuery({
    queryKey: ['trafficHistory', timeWindow],
    queryFn: () => api.analytics.getTraffic(timeWindow),
  });

  const history = traffic?.history || [];
  const maxDown = history.length ? Math.max(...history.map((h: any) => h.download_mbps || 0)) : 0;
  const maxUp = history.length ? Math.max(...history.map((h: any) => h.upload_mbps || 0)) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Usage Analytics
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Historical bandwidth consumption and throughput telemetry.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
            {[
              { label: '24 Hours', hours: 24 },
              { label: '7 Days', hours: 168 },
              { label: '30 Days', hours: 720 },
            ].map((w) => (
              <button
                key={w.hours}
                onClick={() => setTimeWindow(w.hours)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  timeWindow === w.hours
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>

          <a
            href="/api/v1/analytics/export?days=7"
            download
            className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl text-sm font-medium hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 transition-colors"
          >
            <Download className="w-4 h-4 mr-2" /> Export CSV
          </a>
        </div>
      </div>

      {/* Aggregate Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatusCard
          title="Peak Download Speed"
          value={formatMbps(maxDown)}
          subtitle="Highest recorded rate"
          icon={ArrowDown}
          iconColor="text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60"
        />
        <StatusCard
          title="Peak Upload Speed"
          value={formatMbps(maxUp)}
          subtitle="Highest recorded rate"
          icon={ArrowUp}
          iconColor="text-sky-600 bg-sky-50 dark:bg-sky-950/60"
        />
        <StatusCard
          title="Historical Samples"
          value={history.length}
          subtitle={`Window: ${timeWindow} hours`}
          icon={Zap}
          iconColor="text-amber-600 bg-amber-50 dark:bg-amber-950/60"
        />
      </div>

      {/* Interactive Chart */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-4">
          Throughput History Curve
        </h3>
        <BandwidthAreaChart data={history} />
      </div>
    </div>
  );
};

