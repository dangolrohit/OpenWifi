import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Wifi, RefreshCw, Lock, ShieldCheck, AlertTriangle } from 'lucide-react';
import { Button } from '@/elements/buttons/Button';
import { Badge } from '@/elements/badges/Badge';
import { api } from '@/services/api';

export const WifiPage: React.FC = () => {
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['wifiStatus'],
    queryFn: api.wifi.getStatus,
  });

  const { data: scanData, isLoading: scanLoading, refetch: rescan } = useQuery({
    queryKey: ['wifiScan'],
    queryFn: api.wifi.scan,
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Wi-Fi Settings
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Manage Ubuntu laptop's upstream wireless interface and observe nearby networks.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            refetchStatus();
            rescan();
          }}
          isLoading={scanLoading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Rescan Networks
        </Button>
      </div>

      {/* Primary Connection Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-brand-950/60 text-brand-600 dark:text-brand-400 flex items-center justify-center">
              <Wifi className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                {status?.ssid || 'Searching for connection...'}
              </h3>
              <p className="text-xs text-slate-500">
                Interface: {status?.interface || 'wlp2s0'} · BSSID: {status?.bssid || 'N/A'}
              </p>
            </div>
          </div>
          <Badge variant={status?.connected ? 'success' : 'danger'}>
            {status?.connected ? 'Connected & Active' : 'Disconnected'}
          </Badge>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-slate-100 dark:border-slate-800 text-sm">
          <div>
            <p className="text-xs text-slate-500">Signal Strength</p>
            <p className="font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
              {status?.signal_percent || 0}% ({status?.signal_dbm || -100} dBm)
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Frequency & Channel</p>
            <p className="font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
              CH {status?.channel || 36} ({status?.frequency_mhz || 5000} MHz)
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Local IP / Subnet</p>
            <p className="font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
              {status?.ip || '192.168.1.100'} / 24
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Security Mode</p>
            <p className="font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
              {status?.security || 'WPA2-PSK'}
            </p>
          </div>
        </div>
      </div>

      {/* Safety Notice */}
      <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 rounded-2xl p-4 text-sm text-amber-800 dark:text-amber-300 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
        <div>
          <p className="font-bold">Important Network Separation Notice</p>
          <p className="text-xs mt-1 leading-relaxed">
            This page manages the upstream Wi-Fi connection between the Ubuntu laptop and your primary internet router.
            Secondary router guest Wi-Fi settings (SSID and guest password) are managed on your secondary router's hardware web interface.
          </p>
        </div>
      </div>

      {/* Scanned Access Points */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-4">
          Nearby Wireless Networks
        </h3>

        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {(scanData?.networks || []).map((net) => (
            <div key={net.bssid} className="py-3.5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Wifi className="w-4 h-4 text-slate-400" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">{net.ssid}</span>
                    {net.in_use && <Badge variant="success">Current Network</Badge>}
                  </div>
                  <span className="text-xs text-slate-500">CH {net.channel} · {net.security}</span>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{net.signal_percent}%</span>
                  <p className="text-slate-400">Signal</p>
                </div>
                {!net.in_use && (
                  <Button variant="outline" size="sm" onClick={() => alert(`Connect dialog for ${net.ssid}`)}>
                    Connect
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

