import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Sidebar } from '@/components/navigation/Sidebar';
import { Header } from '@/components/navigation/Header';
import { api } from '@/services/api';

export const AdminLayout: React.FC = () => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Poll live bandwidth telemetry every 3 seconds for header counters
  const { data: bandwidth } = useQuery({
    queryKey: ['liveBandwidth'],
    queryFn: api.bandwidth.getLive,
    refetchInterval: 3000,
  });

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 overflow-hidden font-sans">
      {/* Mobile sidebar overlay */}
      {isMobileSidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/50 backdrop-blur-sm md:hidden"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* Persistent / Responsive Sidebar */}
      <div className={isMobileSidebarOpen ? 'fixed inset-y-0 left-0 z-40' : 'hidden md:flex'}>
        <Sidebar isOpen={true} onClose={() => setIsMobileSidebarOpen(false)} />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header
          onMenuToggle={() => setIsMobileSidebarOpen((prev) => !prev)}
          downloadSpeed={bandwidth?.download_mbps || 0}
          uploadSpeed={bandwidth?.upload_mbps || 0}
        />
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

