import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users,
  Ticket,
  Clock,
  Plus,
  Trash2,
  RotateCcw,
  ShieldCheck,
  CheckCircle,
} from 'lucide-react';
import { api } from '@/services/api';
import { HotspotPlan, Voucher, GuestSession } from '@/types';
import { Button } from '@/elements/buttons/Button';
import { Badge } from '@/elements/badges/Badge';
import { StatusCard } from '@/components/common/StatusCard';

export const GuestsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [newVoucherPlan, setNewVoucherPlan] = useState('standard');
  const [customCode, setCustomCode] = useState('');

  const { data: plans = [], isLoading: plansLoading } = useQuery({
    queryKey: ['hotspotPlans'],
    queryFn: api.guests.getPlans,
  });

  const { data: vouchers = [] } = useQuery({
    queryKey: ['vouchers'],
    queryFn: api.guests.getVouchers,
    refetchInterval: 5000,
  });

  const { data: sessions = [] } = useQuery({
    queryKey: ['guestSessions'],
    queryFn: api.guests.getSessions,
    refetchInterval: 3000,
  });

  const createVoucherMutation = useMutation({
    mutationFn: () => api.guests.createVoucher(newVoucherPlan, customCode || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] });
      setCustomCode('');
    },
  });

  const deleteVoucherMutation = useMutation({
    mutationFn: (code: string) => api.guests.deleteVoucher(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] });
    },
  });

  const extendSessionMutation = useMutation({
    mutationFn: (ip: string) => api.guests.extendSession(ip, 30),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guestSessions'] });
    },
  });

  const revokeSessionMutation = useMutation({
    mutationFn: (ip: string) => api.guests.revokeSession(ip),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guestSessions'] });
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Guest Management & Captive Hotspot
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Configure hotspot plans, generate voucher PINs, and control live customer Wi-Fi sessions.
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatusCard
          title="Active Guest Sessions"
          value={sessions.length}
          subtitle="Currently authorized clients"
          icon={Users}
          iconColor="text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60"
        />
        <StatusCard
          title="Available Vouchers"
          value={vouchers.filter((v) => !v.is_used).length}
          subtitle={`${vouchers.filter((v) => v.is_used).length} redeemed`}
          icon={Ticket}
          iconColor="text-brand-600 bg-brand-50 dark:bg-brand-950/60"
        />
        <StatusCard
          title="Hotspot Plans"
          value={plans.length}
          subtitle="Tiered access profiles"
          icon={Clock}
          iconColor="text-purple-600 bg-purple-50 dark:bg-purple-950/60"
        />
      </div>

      {/* Active Guest Sessions Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
            Active Guest Sessions
          </h3>
          <span className="text-xs text-slate-500">Auto-expires via background maintenance</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3">Client IP</th>
                <th className="px-6 py-3">Plan</th>
                <th className="px-6 py-3">Speed Limit</th>
                <th className="px-6 py-3">Expires At</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {sessions.map((s) => (
                <tr key={s.ip}>
                  <td className="px-6 py-3.5 font-mono font-medium">{s.ip}</td>
                  <td className="px-6 py-3.5">
                    <Badge variant="info">{s.plan_id.toUpperCase()}</Badge>
                  </td>
                  <td className="px-6 py-3.5 font-semibold text-xs text-slate-700 dark:text-slate-300">
                    {s.speed_limit_mbps > 0 ? `${s.speed_limit_mbps} Mbps` : 'Unlimited'}
                  </td>
                  <td className="px-6 py-3.5 text-xs text-slate-500">
                    {new Date(s.expires_at).toLocaleTimeString()}
                  </td>
                  <td className="px-6 py-3.5 text-right space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => extendSessionMutation.mutate(s.ip)}
                      isLoading={extendSessionMutation.isPending}
                    >
                      +30m
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => revokeSessionMutation.mutate(s.ip)}
                      isLoading={revokeSessionMutation.isPending}
                    >
                      Revoke
                    </Button>
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                    No active guest sessions. Unauthenticated visitors are held at the captive portal.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Hotspot Plans Grid */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-4">
          Tiered Hotspot Plans
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {plans.map((p) => (
            <div
              key={p.plan_id}
              className={`p-4 rounded-xl border ${
                p.plan_id === 'starter'
                  ? 'border-brand-500 bg-brand-50/50 dark:bg-brand-950/20'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  {p.type}
                </span>
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
              </div>
              <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">{p.name}</h4>
              <div className="mt-2 space-y-1 text-xs text-slate-600 dark:text-slate-300">
                <p>⏱ {p.duration_minutes} Mins</p>
                <p>⚡ {p.speed_limit_mbps} Mbps Limit</p>
              </div>
              <p className="text-[11px] text-slate-400 mt-2 line-clamp-2">{p.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Voucher Generator & List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-3">
            Generate Access Voucher
          </h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createVoucherMutation.mutate();
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Select Plan
              </label>
              <select
                value={newVoucherPlan}
                onChange={(e) => setNewVoucherPlan(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
              >
                {plans
                  .filter((p) => p.type === 'voucher' && p.is_active)
                  .map((p) => (
                    <option key={p.plan_id} value={p.plan_id}>
                      {p.name} ({p.duration_minutes}m, {p.speed_limit_mbps} Mbps)
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Custom Code (Optional)
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                placeholder="Leave blank for random 6-digit PIN"
                value={customCode}
                onChange={(e) => setCustomCode(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono"
              />
            </div>

            {createVoucherMutation.error && <p role="alert" className="text-sm text-red-600">{createVoucherMutation.error.message}</p>}
            <Button type="submit" isLoading={createVoucherMutation.isPending} className="w-full">
              <Plus className="w-4 h-4 mr-2" /> Generate Voucher PIN
            </Button>
          </form>
        </div>

        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Vouchers Inventory
            </h3>
          </div>
          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-xs font-semibold uppercase tracking-wider sticky top-0">
                <tr>
                  <th className="px-6 py-3">PIN Code</th>
                  <th className="px-6 py-3">Assigned Plan</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {vouchers.map((v) => (
                  <tr key={v.code}>
                    <td className="px-6 py-3 font-mono font-bold tracking-wider text-brand-600 dark:text-brand-400">
                      {v.code}
                    </td>
                    <td className="px-6 py-3 text-xs uppercase text-slate-600 dark:text-slate-300">
                      {v.plan_id}
                    </td>
                    <td className="px-6 py-3">
                      {v.is_used ? (
                        <Badge variant="default">Used by {v.used_by_ip}</Badge>
                      ) : (
                        <Badge variant="success">Available</Badge>
                      )}
                    </td>
                    <td className="px-6 py-3 text-right">
                      {!v.is_used && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => deleteVoucherMutation.mutate(v.code)}
                        >
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

