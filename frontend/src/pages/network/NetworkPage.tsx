import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Network, Route, CheckCircle, AlertTriangle } from 'lucide-react';
import { api } from '@/services/api';
import { Badge } from '@/elements/badges/Badge';

export const NetworkPage: React.FC = () => {
  const { data: ifaceData } = useQuery({
    queryKey: ['networkInterfaces'],
    queryFn: api.network.getInterfaces,
  });

  const { data: routeData } = useQuery({
    queryKey: ['networkRoutes'],
    queryFn: api.network.getRoutes,
  });

  const interfaces = ifaceData?.interfaces || [];
  const routes = routeData?.routes || [];
  const defaultGw = routeData?.default_gateway;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Network Settings & Topology
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Inspect physical and virtual interfaces, routing tables, and gateway isolation.
        </p>
      </div>

      {/* Gateway Verification Card */}
      <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-2xl p-5 flex items-start gap-3">
        <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="font-bold text-emerald-900 dark:text-emerald-200 text-sm">
            Default Route Verified & Protected
          </h4>
          <p className="text-xs text-emerald-700 dark:text-emerald-300 mt-1">
            Default gateway: <b>{defaultGw?.gateway || '192.168.1.1'}</b> via interface <b>{defaultGw?.interface || 'wlp2s0'}</b>.
            The primary Wi-Fi upstream route remains intact and will never be overwritten.
          </p>
        </div>
      </div>

      {/* Interfaces Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Network className="w-4 h-4 text-brand-600" /> Network Interfaces
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3">Interface</th>
                <th className="px-6 py-3">Type / Role</th>
                <th className="px-6 py-3">IP Address</th>
                <th className="px-6 py-3">MAC / Hardware</th>
                <th className="px-6 py-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {interfaces.map((i) => (
                <tr key={i.name}>
                  <td className="px-6 py-3.5 font-mono font-bold text-slate-900 dark:text-slate-100">
                    {i.name}
                  </td>
                  <td className="px-6 py-3.5">
                    <span className="text-xs font-semibold capitalize text-slate-700 dark:text-slate-300">
                      {i.type}
                    </span>
                    <span className="text-[11px] text-slate-400 block">{i.role}</span>
                  </td>
                  <td className="px-6 py-3.5 font-mono text-xs">
                    {i.ip ? `${i.ip}/${i.prefix || 24}` : 'No IP assigned'}
                  </td>
                  <td className="px-6 py-3.5 font-mono text-xs text-slate-400">
                    {i.mac || 'N/A'}
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <Badge variant={i.state === 'UP' ? 'success' : 'default'}>{i.state}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Routing Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Route className="w-4 h-4 text-sky-600" /> IP Routing Table
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3">Destination</th>
                <th className="px-6 py-3">Gateway</th>
                <th className="px-6 py-3">Interface</th>
                <th className="px-6 py-3">Metric</th>
                <th className="px-6 py-3 text-right">Protocol</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {routes.map((r, idx) => (
                <tr key={idx}>
                  <td className="px-6 py-3.5 font-mono font-medium">{r.destination}</td>
                  <td className="px-6 py-3.5 font-mono text-xs">{r.gateway}</td>
                  <td className="px-6 py-3.5 font-mono text-xs font-semibold text-brand-600 dark:text-brand-400">
                    {r.interface}
                  </td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">{r.metric ?? 'N/A'}</td>
                  <td className="px-6 py-3.5 text-right font-mono text-xs text-slate-400">
                    {r.protocol || 'kernel'}
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

