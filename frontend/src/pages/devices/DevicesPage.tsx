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
  CheckCircle,
} from 'lucide-react';
import { Device } from '@/types';
import { api } from '@/services/api';
import { Badge } from '@/elements/badges/Badge';
import { Button } from '@/elements/buttons/Button';
import { Modal } from '@/components/common/Modal';

export const DevicesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<string>('all');
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);

  const { data: devices = [], isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: api.devices.list,
    refetchInterval: 5000,
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

  const filteredDevices = devices.filter((d) => {
    const matchesSearch =
      (d.nickname || '').toLowerCase().includes(search.toLowerCase()) ||
      (d.hostname || '').toLowerCase().includes(search.toLowerCase()) ||
      d.ip.includes(search) ||
      d.mac.toLowerCase().includes(search.toLowerCase());

    const matchesGroup =
      groupFilter === 'all' ||
      (groupFilter === 'blocked' ? d.is_blocked : d.group === groupFilter);

    return matchesSearch && matchesGroup;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Connected Devices
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Monitor and configure individual connected devices, bandwidth limits, and curfew access rules.
        </p>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search by nickname, IP, MAC address..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm focus:outline-none focus:border-brand-500"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          {['all', 'family', 'customer', 'staff', 'blocked'].map((g) => (
            <button
              key={g}
              onClick={() => setGroupFilter(g)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors ${
                groupFilter === g
                  ? 'bg-brand-600 text-white'
                  : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:bg-slate-50'
              }`}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {/* Devices Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-6 py-3.5">Device Identity</th>
                <th className="px-6 py-3.5">IP / MAC</th>
                <th className="px-6 py-3.5">Network Group</th>
                <th className="px-6 py-3.5">Policy / Limits</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filteredDevices.map((d) => (
                <tr key={d.ip} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300">
                        <Smartphone className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="font-semibold text-slate-900 dark:text-slate-100">
                          {d.nickname || d.hostname || 'Unnamed Device'}
                        </div>
                        <div className="text-xs text-slate-400">{d.vendor || 'Unknown Vendor'}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-mono text-xs font-medium text-slate-900 dark:text-slate-100">{d.ip}</div>
                    <div className="font-mono text-[11px] text-slate-400">{d.mac}</div>
                  </td>
                  <td className="px-6 py-4">
                    <Badge
                      variant={
                        d.group === 'family' ? 'success' : d.group === 'customer' ? 'warning' : 'info'
                      }
                    >
                      {d.group.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="px-6 py-4">
                    <div className="space-y-1 text-xs">
                      {d.speed_limit_mbps > 0 ? (
                        <span className="flex items-center gap-1 text-sky-600 dark:text-sky-400 font-semibold">
                          <Gauge className="w-3.5 h-3.5" /> {d.speed_limit_mbps} Mbps Limit
                        </span>
                      ) : (
                        <span className="text-slate-400">Unlimited Speed</span>
                      )}
                      {d.schedule_enabled && (
                        <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400 font-semibold">
                          <Clock className="w-3.5 h-3.5" /> Curfew: {d.schedule_start}–{d.schedule_end}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {d.is_blocked ? (
                      <Badge variant="danger">BLOCKED</Badge>
                    ) : (
                      <Badge variant="success">ONLINE</Badge>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
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
              updateMutation.mutate({
                ip: editingDevice.ip,
                updates: {
                  nickname: fd.get('nickname') as string,
                  group: fd.get('group') as string,
                  speed_limit_mbps: parseInt(fd.get('speed_limit') as string, 10) || 0,
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

