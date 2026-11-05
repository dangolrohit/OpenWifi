import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ScrollText, Globe, Trash2, Search } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/elements/buttons/Button';
import { Badge } from '@/elements/badges/Badge';

export const LogsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'audit' | 'dns'>('audit');
  const [filterClient, setFilterClient] = useState('');

  const { data: auditLogs = [], isLoading: auditLoading } = useQuery({
    queryKey: ['auditLogs'],
    queryFn: () => api.logs.getAuditLogs(100),
    refetchInterval: 10000,
  });

  const { data: dnsData, isLoading: dnsLoading } = useQuery({
    queryKey: ['dnsActivity', filterClient],
    queryFn: () => api.logs.getDnsActivity(filterClient || undefined),
    refetchInterval: 5000,
  });

  const clearDnsMutation = useMutation({
    mutationFn: api.logs.clearDnsActivity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dnsActivity'] });
    },
  });

  const queries = dnsData?.queries || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System & Network Logs
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Audit trail of administrator actions, session events, and gateway DNS lookups.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'audit'
                ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
                : 'text-slate-600 dark:text-slate-400'
            }`}
          >
            <ScrollText className="w-3.5 h-3.5" /> Audit History
          </button>
          <button
            onClick={() => setActiveTab('dns')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'dns'
                ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
                : 'text-slate-600 dark:text-slate-400'
            }`}
          >
            <Globe className="w-3.5 h-3.5" /> DNS Activity
          </button>
        </div>
      </div>

      {activeTab === 'audit' ? (
        /* Audit Logs Table */
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Timestamp</th>
                  <th className="px-6 py-3.5">Actor</th>
                  <th className="px-6 py-3.5">Event Type</th>
                  <th className="px-6 py-3.5">Description</th>
                  <th className="px-6 py-3.5">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-6 py-3.5 text-xs text-slate-500 whitespace-nowrap">
                      {new Date(log.recorded_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-3.5 font-medium text-slate-900 dark:text-slate-100 whitespace-nowrap">
                      {log.actor}
                    </td>
                    <td className="px-6 py-3.5 font-mono text-xs font-semibold text-brand-600 dark:text-brand-400 whitespace-nowrap">
                      {log.event_type}
                    </td>
                    <td className="px-6 py-3.5 text-slate-600 dark:text-slate-300 text-xs">
                      {log.description}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <Badge
                        variant={
                          log.severity === 'error'
                            ? 'danger'
                            : log.severity === 'warning'
                            ? 'warning'
                            : 'info'
                        }
                      >
                        {log.severity.toUpperCase()}
                      </Badge>
                    </td>
                  </tr>
                ))}
                {auditLogs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                      No audit events recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* DNS Activity Table */
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="Filter by client IP (e.g. 192.168.16.105)..."
                value={filterClient}
                onChange={(e) => setFilterClient(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => clearDnsMutation.mutate()}
              isLoading={clearDnsMutation.isPending}
            >
              <Trash2 className="w-4 h-4 mr-1.5 text-red-500" /> Clear Query Logs
            </Button>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider sticky top-0">
                  <tr>
                    <th className="px-6 py-3">Timestamp</th>
                    <th className="px-6 py-3">Client Device</th>
                    <th className="px-6 py-3">Domain Looked Up</th>
                    <th className="px-6 py-3">Query Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {queries.map((q, idx) => (
                    <tr key={idx}>
                      <td className="px-6 py-3 text-xs text-slate-500">{q.timestamp}</td>
                      <td className="px-6 py-3 font-mono font-medium text-xs">{q.client}</td>
                      <td className="px-6 py-3 font-semibold text-slate-900 dark:text-slate-100 text-xs">
                        {q.domain}
                      </td>
                      <td className="px-6 py-3">
                        <Badge variant="default">{q.type}</Badge>
                      </td>
                    </tr>
                  ))}
                  {queries.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-6 py-8 text-center text-slate-400 text-xs">
                        No DNS queries captured. Ensure dnsmasq query logging is active.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

