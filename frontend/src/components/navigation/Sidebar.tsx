import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Wifi,
  Smartphone,
  ShieldAlert,
  BarChart3,
  Users,
  ScrollText,
  Network,
  Activity,
  Settings as SettingsIcon,
  LogOut,
  Radio,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useAuth } from '@/hooks/useAuth';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Wi-Fi Settings', path: '/wifi', icon: Wifi },
  { name: 'Connected Devices', path: '/devices', icon: Smartphone },
  { name: 'Device Filtering', path: '/filtering', icon: ShieldAlert },
  { name: 'Usage Analytics', path: '/analytics', icon: BarChart3 },
  { name: 'Guest Management', path: '/guests', icon: Users },
  { name: 'User Logs', path: '/logs', icon: ScrollText },
  { name: 'Network Settings', path: '/network', icon: Network },
  { name: 'System Monitoring', path: '/system', icon: Activity },
  { name: 'Settings', path: '/settings', icon: SettingsIcon },
];

export const Sidebar: React.FC<{ isOpen?: boolean; onClose?: () => void }> = ({
  isOpen = true,
  onClose,
}) => {
  const { logout, user } = useAuth();

  return (
    <aside
      className={cn(
        'w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 transition-all duration-300 z-40',
        isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      )}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800">
        <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center text-white shadow-md shadow-brand-500/20">
          <Radio className="w-5 h-5 animate-pulse" />
        </div>
        <div>
          <h1 className="text-base font-bold text-white tracking-tight">WiFiRouter</h1>
          <span className="text-[10px] uppercase font-bold text-brand-400 tracking-wider">
            Network OS V2
          </span>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-600 text-white shadow-sm shadow-brand-500/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
              )
            }
          >
            <item.icon className="w-4 h-4 flex-shrink-0" />
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      {/* User info and Logout Footer */}
      <div className="p-3 border-t border-slate-800">
        <div className="px-3 py-2 mb-2 bg-slate-800/50 rounded-lg flex items-center justify-between">
          <div className="truncate">
            <p className="text-xs font-semibold text-white truncate">{user?.username || 'admin'}</p>
            <p className="text-[10px] text-slate-400 uppercase tracking-wider">{user?.role || 'administrator'}</p>
          </div>
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
        </div>
        <button
          onClick={() => logout()}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-950/30 transition-colors"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};

