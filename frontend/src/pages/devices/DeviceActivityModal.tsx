import { useEffect, useId, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, RefreshCw } from 'lucide-react';
import { Device } from '@/types';
import { api } from '@/services/api';
import { Button } from '@/elements/buttons/Button';

export function DeviceActivityModal({ device, onClose }: { device: Device; onClose: () => void }) {
  const [page, setPage] = useState(1);
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['deviceActivity', device.ip, page],
    queryFn: () => api.logs.getDeviceActivity(device.ip, page),
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));

  return (
    <dialog ref={dialog} aria-labelledby={titleId} onCancel={onClose}
      className="m-auto w-[calc(100%-2rem)] max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-900/60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
        <div>
          <h3 id={titleId} className="text-lg font-bold">Device Internet Activity</h3>
          <p className="text-sm text-slate-500">{device.nickname || device.hostname || 'Unnamed Device'} · {device.ip}</p>
          <p className="text-xs text-slate-500">{device.mac}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close activity"><X className="h-5 w-5" /></Button>
      </div>
      <div className="space-y-4 p-6">
        <p className="text-sm text-slate-500">
          Recorded DNS requests for this IP, newest first. These include app and background lookups,
          not confirmed page visits. Full HTTPS URLs and page paths are not visible. Cached lookups,
          encrypted DNS and VPN traffic may be absent. History is limited to retained gateway logs;
          an IP reassigned to another device can include its earlier activity.
        </p>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium">{data ? `${data.total} recorded requests` : 'Device requests'}</span>
          <Button variant="outline" size="sm" isLoading={isFetching} onClick={() => { if (page === 1) void refetch(); else setPage(1); }}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>
        {data?.simulated && <p className="text-sm text-amber-600">Simulation mode: demonstration activity only.</p>}
        {error && <p role="alert" className="text-sm text-red-600">Could not load activity: {error.message}</p>}
        {isFetching && <p role="status" className="text-sm text-slate-500">Loading activity...</p>}
        {!error && data && (
          <>
            <div className="overflow-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr><th scope="col" className="px-4 py-3">Time (gateway)</th><th scope="col" className="px-4 py-3">Requested domain</th><th scope="col" className="px-4 py-3">DNS type</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {data.queries.map((query, index) => (
                    <tr key={`${page}-${index}`}>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">{query.timestamp}</td>
                      <td className="break-all px-4 py-3 font-medium">{query.domain}</td>
                      <td className="px-4 py-3 font-mono text-xs">{query.type}</td>
                    </tr>
                  ))}
                  {data.queries.length === 0 && <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-500">
                    {!data.log_available ? 'DNS logs are unavailable. Enable dnsmasq query logging on Ubuntu.' : page > 1 ? 'No requests on this page. Refresh to return to the latest activity.' : 'No recorded DNS requests for this device. Ensure it uses the gateway DNS and query logging is enabled.'}
                  </td></tr>}
                </tbody>
              </table>
            </div>
            {(data.total > 20 || page > 1) && (
              <nav aria-label="Device activity pagination" className="flex flex-wrap items-center justify-between gap-3">
                <Button variant="outline" size="sm" disabled={page === 1 || isFetching} onClick={() => setPage(p => p - 1)}>Previous</Button>
                <span className="text-sm text-slate-500" aria-live="polite">Page {page} of {totalPages} · 20 per page</span>
                <Button variant="outline" size="sm" disabled={!data.has_more || isFetching} onClick={() => setPage(p => p + 1)}>Next</Button>
              </nav>
            )}
          </>
        )}
        {error && page > 1 && <Button variant="outline" onClick={() => setPage(p => p - 1)}>Previous page</Button>}
      </div>
    </dialog>
  );
}
