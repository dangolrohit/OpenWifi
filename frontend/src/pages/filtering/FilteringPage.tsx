import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldAlert, ShieldCheck, Plus, Trash2, Lock, Users } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/elements/buttons/Button';
import { Badge } from '@/elements/badges/Badge';

export const FilteringPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [newIp, setNewIp] = useState('');

  const { data: status, isLoading } = useQuery({
    queryKey: ['filteringStatus'],
    queryFn: api.filtering.getStatus,
    refetchInterval: 5000,
  });

  const blockMutation = useMutation({
    mutationFn: (ip: string) => api.filtering.block(ip),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['filteringStatus'] });
      setNewIp('');
    },
  });

  const unblockMutation = useMutation({
    mutationFn: (ip: string) => api.filtering.unblock(ip),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['filteringStatus'] });
    },
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Device Filtering & Firewall
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manage hardware-enforced packet filtering rules, blocklists, and customer isolation sets.
        </p>
      </div>

      {/* Manual Block Form */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-3">
          Block Device by IP Address
        </h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (newIp.trim()) blockMutation.mutate(newIp.trim());
          }}
          className="flex flex-col sm:flex-row gap-3 max-w-xl"
        >
          <input
            type="text"
            required
            placeholder="e.g. 192.168.16.105"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
            className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:border-brand-500"
          />
          <Button type="submit" variant="danger" isLoading={blockMutation.isPending}>
            <Plus className="w-4 h-4 mr-1.5" /> Block Address
          </Button>
        </form>
      </div>

      {/* Active Sets Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Blocked List Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-500" /> Blocked List
            </h3>
            <Badge variant="danger">{(status?.blocked || []).length} Blocked</Badge>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-80 overflow-y-auto">
            {(status?.blocked || []).map((ip: string) => (
              <div key={ip} className="py-2.5 flex items-center justify-between text-sm">
                <span className="font-mono font-medium">{ip}</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => unblockMutation.mutate(ip)}
                  isLoading={unblockMutation.isPending}
                >
                  Unblock
                </Button>
              </div>
            ))}
            {(status?.blocked || []).length === 0 && (
              <p className="text-xs text-slate-400 py-6 text-center">No addresses currently blocked.</p>
            )}
          </div>
        </div>

        {/* Customer Isolation Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Lock className="w-4 h-4 text-amber-500" /> Customer Isolation
            </h3>
            <Badge variant="warning">{(status?.customers || []).length} Isolated</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
            Addresses blocked from accessing admin port 8090 and isolated from communicating with LAN peers.
          </p>
          <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-60 overflow-y-auto">
            {(status?.customers || []).map((ip: string) => (
              <div key={ip} className="py-2 font-mono text-sm text-slate-700 dark:text-slate-300">
                {ip}
              </div>
            ))}
            {(status?.customers || []).length === 0 && (
              <p className="text-xs text-slate-400 py-4 text-center">No devices tagged as Customer.</p>
            )}
          </div>
        </div>

        {/* Whitelisted Family Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-500" /> Whitelisted Sets
            </h3>
            <Badge variant="success">{(status?.whitelisted || []).length} Whitelisted</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
            Family and staff devices that bypass the captive portal completely with unhindered internet forwarding.
          </p>
          <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-60 overflow-y-auto">
            {(status?.whitelisted || []).map((ip: string) => (
              <div key={ip} className="py-2 font-mono text-sm text-slate-700 dark:text-slate-300">
                {ip}
              </div>
            ))}
            {(status?.whitelisted || []).length === 0 && (
              <p className="text-xs text-slate-400 py-4 text-center">No whitelisted devices.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

