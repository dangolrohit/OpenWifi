import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Smartphone,
  Search,
  Filter,
  Shield,
  ShieldAlert,
  Clock,
  Gauge,
  Edit2,
  Eye,
  CheckCircle,
  Wifi,
  AlertTriangle,
  Lock,
  PlusCircle,
  Zap,
  XCircle,
  Radio,
  RefreshCw,
} from 'lucide-react';
import { Device, HotspotPlan } from '@/types';
import { api } from '@/services/api';
import { Badge } from '@/elements/badges/Badge';
import { Button } from '@/elements/buttons/Button';
import { Modal } from '@/components/common/Modal';
import { DeviceActivityModal } from './DeviceActivityModal';

export const DevicesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [viewingDevice, setViewingDevice] = useState<Device | null>(null);

  const { data: devices = [], isLoading, isFetching } = useQuery({
    queryKey: ['devices'],
    queryFn: api.devices.list,
    refetchInterval: 3000,
  });

  const { data: plans = [] } = useQuery({
    queryKey: ['hotspotPlans'],
    queryFn: api.guests.getPlans,
  });

  const updateMutation = useMutation({
    mutationFn: ({ ip, updates }: { ip: string; updates: any }) => api.devices.update(ip, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setEditingDevice(null);
    },
  });

  const blockMutation = useMutation({
    mutationFn: ({ ip, blocked }: { ip: string; blocked: boolean }) => api.devices.block(ip, blocked),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  const grantMutation = useMutation({
    mutationFn: ({ ip, plan_id }: { ip: string; plan_id: string }) =>
      api.devices.grantPlan(ip, plan_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  const extendMutation = useMutation({
    mutationFn: ({ ip, minutes }: { ip: string; minutes: number }) =>
      api.devices.extendTime(ip, minutes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (ip: string) => api.devices.revokeInternet(ip),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  // Calculate statistics
  const totalCount = devices.length;
  const liveConnectedDevices = devices.filter((d) => d.is_online);
  const liveConnectedCount = liveConnectedDevices.length;
  const activeCount = devices.filter((d) => d.internet_status === 'active' || d.internet_status === 'unlimited').length;
  const expiredCount = devices.filter((d) => d.internet_status === 'expired').length;
  const captiveCount = devices.filter((d) => d.internet_status === 'unauthorized').length;
  const blockedCount = devices.filter((d) => d.is_blocked).length;

  const filteredDevices = devices.filter((d) => {
    const matchesSearch =
      (d.nickname || '').toLowerCase().includes(search.toLowerCase()) ||
      (d.hostname || '').toLowerCase().includes(search.toLowerCase()) ||
      d.ip.includes(search) ||
      d.mac.toLowerCase().includes(search.toLowerCase()) ||
      (d.plan_name || '').toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;

    if (filterType === 'all') return true;
    if (filterType === 'online') return !!d.is_online;
    if (filterType === 'active') return d.internet_status === 'active' || d.internet_status === 'unlimited';
    if (filterType === 'expired') return d.internet_status === 'expired';
    if (filterType === 'captive') return d.internet_status === 'unauthorized';
    if (filterType === 'family') return d.group === 'family' || d.group === 'staff';
    if (filterType === 'customer') return d.group === 'customer';
    if (filterType === 'blocked') return d.is_blocked;

    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Connected Devices
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Real-time connected device tracking, live hotspot plans, time limits, and internet access policies.
        </p>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Discovered</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{totalCount}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Known Device History</p>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-900/40 rounded-2xl p-4 shadow-sm bg-gradient-to-br from-white to-emerald-50/30 dark:from-slate-900 dark:to-emerald-950/20">
          <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 animate-pulse" /> Online Now
          </p>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">{liveConnectedCount}</p>
          <p className="text-[11px] text-emerald-600/70 dark:text-emerald-400/70 mt-0.5">Connected on Wi-Fi/LAN</p>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-sky-600 dark:text-sky-400 uppercase tracking-wider flex items-center gap-1.5">
            <Wifi className="w-3.5 h-3.5" /> Internet Active
          </p>
          <p className="text-2xl font-bold text-sky-600 dark:text-sky-400 mt-1">{activeCount}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Whitelisted / Authorized</p>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> Time Exceeded
          </p>
          <p className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">{expiredCount}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Plan expired · Disconnected</p>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm">
          <p className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" /> Captive Gate
          </p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1">{captiveCount}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Needs Login / Voucher</p>
        </div>
      </div>

      {/* Real-Time Connected Devices Section */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Live Connected Devices
            </h3>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
              {liveConnectedCount} Currently Connected
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Real-time sync (3s)
            </span>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['devices'] })}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
              title="Rescan and refresh connected devices right now"
            >
              <RefreshCw className={`w-3 h-3 ${isFetching ? 'animate-spin text-brand-500' : ''}`} />
              Scan Now
            </button>
          </div>
        </div>

        {liveConnectedCount > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {liveConnectedDevices.map((d) => (
              <div
                key={d.ip}
                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-emerald-400/60 dark:hover:border-emerald-500/50 rounded-2xl p-4 shadow-sm transition-all"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/40 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
                      <Smartphone className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-semibold text-sm text-slate-900 dark:text-slate-100 truncate">
                        {d.nickname || d.hostname || 'Unnamed Client'}
                      </h4>
                      <p className="text-xs text-slate-400 truncate">{d.vendor || 'LAN Device'}</p>
                    </div>
                  </div>

                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/50 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Online
                  </span>
                </div>

                {/* Network & Plan Details */}
                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">IP / MAC:</span>
                    <span className="font-mono font-medium text-slate-700 dark:text-slate-300 text-[11px]">
                      {d.ip} · {d.mac}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Internet Policy:</span>
                    <div>
                      {d.is_blocked ? (
                        <Badge variant="danger" className="text-[10px] py-0">Blocked</Badge>
                      ) : d.internet_status === 'unlimited' ? (
                        <Badge variant="success" className="text-[10px] py-0">Whitelisted</Badge>
                      ) : d.internet_status === 'active' ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                          <CheckCircle className="w-3 h-3" /> {d.time_remaining_str || 'Active'}
                        </span>
                      ) : d.internet_status === 'expired' ? (
                        <Badge variant="danger" className="text-[10px] py-0">Expired</Badge>
                      ) : (
                        <Badge variant="warning" className="text-[10px] py-0">Captive Gate</Badge>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Speed / QoS:</span>
                    <span className="font-medium text-slate-700 dark:text-slate-300 text-xs">
                      {d.speed_limit_mbps > 0 ? `${d.speed_limit_mbps} Mbps Limit` : 'Full Speed'}
                    </span>
                  </div>
                </div>

                {/* Quick Actions */}
                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5">
                    {d.internet_status === 'active' ? (
                      <>
                        <button
                          onClick={() => extendMutation.mutate({ ip: d.ip, minutes: 30 })}
                          className="px-2 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 hover:bg-emerald-100 rounded-lg transition-colors"
                          title="Add 30 minutes to current session"
                        >
                          +30m
                        </button>
                        <button
                          onClick={() => revokeMutation.mutate(d.ip)}
                          className="px-2 py-1 text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/50 hover:bg-rose-100 rounded-lg transition-colors"
                          title="Revoke session / disconnect internet"
                        >
                          Cut Off
                        </button>
                      </>
                    ) : (d.internet_status === 'expired' || d.internet_status === 'unauthorized') && !d.is_blocked ? (
                      <button
                        onClick={() => grantMutation.mutate({ ip: d.ip, plan_id: 'starter' })}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 hover:bg-emerald-100 rounded-lg transition-colors"
                        title="Grant 30 minutes Starter Plan"
                      >
                        <Zap className="w-3 h-3" /> Grant 30m
                      </button>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setViewingDevice(d)}
                      className="p-1.5 text-slate-500 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                      title="Inspect DNS & Traffic Activity"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setEditingDevice(d)}
                      className="p-1.5 text-slate-500 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                      title="Edit Device Settings"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => blockMutation.mutate({ ip: d.ip, blocked: !d.is_blocked })}
                      className={`p-1.5 rounded-lg transition-colors ${
                        d.is_blocked
                          ? 'text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50'
                          : 'text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50'
                      }`}
                      title={d.is_blocked ? 'Unblock device' : 'Block device'}
                    >
                      <ShieldAlert className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-900 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-400 mb-3">
              <Radio className="w-6 h-6 animate-pulse" />
            </div>
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              No Devices Currently Connected
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
              Real-time radar is actively listening on LAN interface <code className="text-brand-500">enp1s0</code> (192.168.16.2). When a phone, laptop, or tablet connects to your Wi-Fi router, it will instantly appear here. When it disconnects, it will automatically disappear.
            </p>
          </div>
        )}
      </div>

      {/* Filter and Search Bar for Full Device Inventory */}
      <div className="pt-2">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search by nickname, IP, MAC address, plan..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm focus:outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
            {[
              { id: 'all', label: `All History (${totalCount})` },
              { id: 'online', label: `🟢 Online (${liveConnectedCount})` },
              { id: 'active', label: `Active (${activeCount})` },
              { id: 'expired', label: `Expired (${expiredCount})` },
              { id: 'captive', label: `Captive (${captiveCount})` },
              { id: 'family', label: 'Family & Staff' },
              { id: 'customer', label: 'Customers' },
              { id: 'blocked', label: `Blocked (${blockedCount})` },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors whitespace-nowrap ${
                  filterType === f.id
                    ? 'bg-brand-600 text-white'
                    : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Devices Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-6 py-3.5">Device Identity</th>
                <th className="px-6 py-3.5">IP Address</th>
                <th className="px-6 py-3.5">Network Group</th>
                <th className="px-6 py-3.5">Hotspot Plan & Limits</th>
                <th className="px-6 py-3.5">Internet Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filteredDevices.map((d) => (
                <tr key={d.ip} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                  {/* Identity */}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="relative w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300">
                        <Smartphone className="w-5 h-5" />
                        {d.is_online ? (
                          <span
                            className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white dark:border-slate-900"
                            title="Online right now"
                          />
                        ) : (
                          <span
                            className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-slate-400 border-2 border-white dark:border-slate-900"
                            title="Offline / Disconnected"
                          />
                        )}
                      </div>
                      <div>
                        <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                          <span>{d.nickname || d.hostname || 'Unnamed Device'}</span>
                          {d.is_online && (
                            <span className="inline-flex items-center px-1.5 py-0.2 text-[10px] font-semibold text-emerald-700 bg-emerald-100 dark:bg-emerald-900/40 dark:text-emerald-300 rounded">
                              LIVE
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400">{d.vendor || 'Unknown Vendor'}</div>
                      </div>
                    </div>
                  </td>

                  {/* IP & MAC */}
                  <td className="px-6 py-4">
                    <div className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100">{d.ip}</div>
                    <div className="font-mono text-[11px] text-slate-400">{d.mac}</div>
                  </td>

                  {/* Network Group */}
                  <td className="px-6 py-4">
                    <Badge
                      variant={
                        d.group === 'family' ? 'success' : d.group === 'customer' ? 'warning' : 'info'
                      }
                    >
                      {d.group.toUpperCase()}
                    </Badge>
                  </td>

                  {/* Plan & Limits */}
                  <td className="px-6 py-4">
                    <div className="space-y-0.5">
                      <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                        {d.plan_name || 'No Plan (Captive Portal)'}
                      </div>

                      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        {d.speed_limit_mbps > 0 ? (
                          <span className="flex items-center gap-1 text-sky-600 dark:text-sky-400 font-medium">
                            <Gauge className="w-3.5 h-3.5" /> {d.speed_limit_mbps} Mbps Limit
                          </span>
                        ) : (
                          <span className="text-slate-400">Unlimited Speed</span>
                        )}
                      </div>

                      {d.schedule_enabled && (
                        <div className="flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400 font-medium">
                          <Clock className="w-3 h-3" /> Curfew: {d.schedule_start}–{d.schedule_end}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Live Internet Access Status */}
                  <td className="px-6 py-4">
                    {d.is_blocked ? (
                      <div>
                        <Badge variant="danger" className="flex items-center gap-1">
                          <ShieldAlert className="w-3 h-3" /> BLOCKED
                        </Badge>
                        <div className="text-[11px] text-rose-500 font-medium mt-0.5">Firewall Drop</div>
                      </div>
                    ) : d.internet_status === 'curfew' ? (
                      <div>
                        <Badge variant="warning" className="flex items-center gap-1">
                          <Clock className="w-3 h-3" /> CURFEW
                        </Badge>
                        <div className="text-[11px] text-amber-600 font-medium mt-0.5">Bedtime Paused</div>
                      </div>
                    ) : d.internet_status === 'unlimited' ? (
                      <div>
                        <Badge variant="success" className="flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> UNLIMITED
                        </Badge>
                        <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium mt-0.5">Whitelisted</div>
                      </div>
                    ) : d.internet_status === 'active' ? (
                      <div>
                        <Badge variant="success" className="flex items-center gap-1">
                          <Wifi className="w-3 h-3" /> ACTIVE
                        </Badge>
                        <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold mt-0.5">
                          {d.time_remaining_str}
                        </div>
                      </div>
                    ) : d.internet_status === 'expired' ? (
                      <div>
                        <Badge variant="danger" className="flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> EXPIRED
                        </Badge>
                        <div className="text-[11px] text-rose-600 dark:text-rose-400 font-bold mt-0.5">
                          Time Limit Exceeded
                        </div>
                      </div>
                    ) : (
                      <div>
                        <Badge variant="warning" className="flex items-center gap-1">
                          <Lock className="w-3 h-3" /> CAPTIVE
                        </Badge>
                        <div className="text-[11px] text-amber-600 dark:text-amber-400 font-medium mt-0.5">
                          Login Required
                        </div>
                      </div>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="px-6 py-4 text-right space-x-1.5 whitespace-nowrap">
                    {/* Quick Hotspot Action */}
                    {d.internet_status === 'active' ? (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => extendMutation.mutate({ ip: d.ip, minutes: 30 })}
                          title="Extend session by +30 minutes"
                        >
                          +30m
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-rose-600 hover:text-rose-700 hover:border-rose-300"
                          onClick={() => revokeMutation.mutate(d.ip)}
                          title="Cut off / revoke internet access"
                        >
                          Revoke
                        </Button>
                      </>
                    ) : (d.internet_status === 'expired' || d.internet_status === 'unauthorized') && !d.is_blocked ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-emerald-600 hover:text-emerald-700 hover:border-emerald-300"
                        onClick={() => grantMutation.mutate({ ip: d.ip, plan_id: 'starter' })}
                        title="Grant 30 minutes free Starter Plan"
                      >
                        <Zap className="w-3.5 h-3.5 mr-1" /> Grant 30m
                      </Button>
                    ) : null}

                    <Button variant="outline" size="sm" onClick={() => setViewingDevice(d)} aria-label={`View activity for ${d.nickname || d.hostname || d.ip}`}>
                      <Eye className="w-3.5 h-3.5" /> View
                    </Button>

                    <Button variant="outline" size="sm" onClick={() => setEditingDevice(d)}>
                      <Edit2 className="w-3.5 h-3.5 mr-1" /> Edit
                    </Button>

                    <Button
                      variant={d.is_blocked ? 'secondary' : 'danger'}
                      size="sm"
                      onClick={() => blockMutation.mutate({ ip: d.ip, blocked: !d.is_blocked })}
                    >
                      {d.is_blocked ? 'Unblock' : 'Block'}
                    </Button>
                  </td>
                </tr>
              ))}
              {filteredDevices.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                    No devices matching search criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {viewingDevice && (
        <DeviceActivityModal key={viewingDevice.ip} device={viewingDevice} onClose={() => setViewingDevice(null)} />
      )}

      {/* Edit Device Modal */}
      {editingDevice && (
        <Modal
          isOpen={!!editingDevice}
          onClose={() => setEditingDevice(null)}
          title={`Configure Device · ${editingDevice.ip}`}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData(e.currentTarget);
              const assignPlan = fd.get('assign_plan') as string;
              updateMutation.mutate({
                ip: editingDevice.ip,
                updates: {
                  nickname: fd.get('nickname') as string,
                  group: fd.get('group') as string,
                  speed_limit_mbps: parseInt(fd.get('speed_limit') as string, 10) || 0,
                  assign_plan_id: assignPlan && assignPlan !== 'none' ? assignPlan : undefined,
                  extend_minutes: assignPlan === 'extend_30' ? 30 : assignPlan === 'extend_60' ? 60 : undefined,
                  revoke_internet: assignPlan === 'revoke',
                  schedule: {
                    enabled: fd.get('sched_enabled') === 'on',
                    start: fd.get('sched_start') as string,
                    end: fd.get('sched_end') as string,
                  },
                },
              });
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Device Nickname
              </label>
              <input
                type="text"
                name="nickname"
                defaultValue={editingDevice.nickname}
                placeholder="e.g. Dad's Phone, Living Room TV"
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Network Group
              </label>
              <select
                name="group"
                defaultValue={editingDevice.group}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
              >
                <option value="family">Family (Bypasses Captive Portal, Permanent Full Speed)</option>
                <option value="customer">Customer (Isolated from LAN devices & Admin Portal)</option>
                <option value="staff">Staff (Whitelisted Work Device)</option>
                <option value="default">Default Guest</option>
              </select>
            </div>

            {/* Hotspot Plan Control */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Hotspot Plan & Access Action
              </label>
              <select
                name="assign_plan"
                defaultValue="none"
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
              >
                <option value="none">-- Keep Current Session / Policy --</option>
                <option value="starter">Grant Starter Plan (Free 30 Minutes)</option>
                <option value="standard">Grant Standard 2-Hour Plan</option>
                <option value="half_day">Grant Half-Day Pass (6 Hours)</option>
                <option value="full_day">Grant Full-Day Pass (24 Hours)</option>
                <option value="vip">Grant VIP Premium Pass (3 Days)</option>
                <option value="extend_30">Add +30 Minutes to Current Session</option>
                <option value="extend_60">Add +60 Minutes to Current Session</option>
                <option value="revoke">Revoke / Cut Off Internet Access Immediately</option>
              </select>
              <span className="text-[11px] text-slate-400 mt-1 block">
                Current Plan: {editingDevice.plan_name || 'No Plan'} · Status: {editingDevice.internet_label || 'Offline'}
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                QoS Speed Limit (Mbps)
              </label>
              <input
                type="number"
                name="speed_limit"
                min="0"
                max="1000"
                defaultValue={editingDevice.speed_limit_mbps}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
              />
              <span className="text-[11px] text-slate-400">Set to 0 for unlimited bandwidth</span>
            </div>

            <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
              <label className="flex items-center gap-2 cursor-pointer mb-2">
                <input
                  type="checkbox"
                  name="sched_enabled"
                  defaultChecked={editingDevice.schedule_enabled}
                  className="rounded text-brand-600 focus:ring-brand-500"
                />
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                  Enable Bedtime / Access Curfew
                </span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-xs text-slate-500">Curfew Start</span>
                  <input
                    type="time"
                    name="sched_start"
                    defaultValue={editingDevice.schedule_start || '22:00'}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm mt-1"
                  />
                </div>
                <div>
                  <span className="text-xs text-slate-500">Curfew End</span>
                  <input
                    type="time"
                    name="sched_end"
                    defaultValue={editingDevice.schedule_end || '06:00'}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm mt-1"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setEditingDevice(null)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={updateMutation.isPending}>
                Save Policy
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
