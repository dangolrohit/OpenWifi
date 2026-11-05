import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Settings, Lock, Download, ShieldCheck, Check, AlertCircle } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/elements/buttons/Button';
import { useAuth } from '@/hooks/useAuth';

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  const { data: settingsData } = useQuery({
    queryKey: ['systemSettings'],
    queryFn: api.settings.getSettings,
  });

  const changePwMutation = useMutation({
    mutationFn: () => api.auth.changePassword(currentPw, newPw),
    onSuccess: () => {
      setPwSuccess(true);
      setPwError(null);
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    },
    onError: (err: any) => {
      setPwError(err.message || 'Failed to change password');
      setPwSuccess(false);
    },
  });

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(false);

    if (newPw.length < 8) {
      setPwError('New password must be at least 8 characters long');
      return;
    }
    if (newPw !== confirmPw) {
      setPwError('New passwords do not match');
      return;
    }
    changePwMutation.mutate();
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Settings & Administration
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manage administrator profile credentials, configuration snapshots, and platform defaults.
        </p>
      </div>

      {/* Change Password Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1 flex items-center gap-2">
          <Lock className="w-4 h-4 text-brand-600" /> Administrator Password
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Secured with Argon2id cryptographic hashing.
        </p>

        {pwSuccess && (
          <div className="mb-4 p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-emerald-800 dark:text-emerald-300 text-xs flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-500" /> Password updated successfully.
          </div>
        )}
        {pwError && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl text-red-800 dark:text-red-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-500" /> {pwError}
          </div>
        )}

        <form onSubmit={handlePasswordSubmit} className="space-y-4 max-w-md">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Current Password
            </label>
            <input
              type="password"
              required
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              New Password
            </label>
            <input
              type="password"
              required
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
              placeholder="Minimum 8 characters"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Confirm New Password
            </label>
            <input
              type="password"
              required
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm"
            />
          </div>

          <Button type="submit" isLoading={changePwMutation.isPending}>
            Update Password
          </Button>
        </form>
      </div>

      {/* Backup and Snapshot Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1 flex items-center gap-2">
          <Download className="w-4 h-4 text-emerald-600" /> Configuration Backup
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Export full router settings, device inventory, and hotspot plan definitions as a sanitized JSON snapshot.
        </p>

        <a
          href="/api/v1/settings/backup"
          download
          className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl text-sm font-medium hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 transition-colors"
        >
          <Download className="w-4 h-4 mr-2" /> Download Backup (JSON)
        </a>
      </div>

      {/* System Information */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm text-sm space-y-3">
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-brand-600" /> System Information
        </h3>
        <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800 text-xs">
          <span className="text-slate-500">Platform Version</span>
          <span className="font-mono font-bold">WiFiRouter V2.0.0</span>
        </div>
        <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800 text-xs">
          <span className="text-slate-500">Operating Environment</span>
          <span className="font-medium">Ubuntu Gateway (wlp2s0 upstream → enp1s0 secondary AP)</span>
        </div>
        <div className="flex justify-between py-1.5 text-xs">
          <span className="text-slate-500">Signed In As</span>
          <span className="font-bold text-brand-600">{user?.username} ({user?.role})</span>
        </div>
      </div>
    </div>
  );
};

