import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AdminLayout } from '@/layouts/AdminLayout';
import { AuthLayout } from '@/layouts/AuthLayout';
import { useAuth } from '@/hooks/useAuth';

import { LoginPage } from '@/pages/auth/LoginPage';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { WifiPage } from '@/pages/wifi/WifiPage';
import { DevicesPage } from '@/pages/devices/DevicesPage';
import { FilteringPage } from '@/pages/filtering/FilteringPage';
import { BandwidthPage } from '@/pages/bandwidth/BandwidthPage';
import { AnalyticsPage } from '@/pages/analytics/AnalyticsPage';
import { GuestsPage } from '@/pages/guests/GuestsPage';
import { LogsPage } from '@/pages/logs/LogsPage';
import { NetworkPage } from '@/pages/network/NetworkPage';
import { SystemPage } from '@/pages/system/SystemPage';
import { SettingsPage } from '@/pages/settings/SettingsPage';
import { NotFoundPage } from '@/pages/errors/NotFoundPage';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <AuthLayout />,
    children: [
      {
        index: true,
        element: <LoginPage />,
      },
    ],
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AdminLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'wifi', element: <WifiPage /> },
      { path: 'devices', element: <DevicesPage /> },
      { path: 'filtering', element: <FilteringPage /> },
      { path: 'bandwidth', element: <BandwidthPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'guests', element: <GuestsPage /> },
      { path: 'logs', element: <LogsPage /> },
      { path: 'network', element: <NetworkPage /> },
      { path: 'system', element: <SystemPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
]);

