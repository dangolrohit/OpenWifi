import React from 'react';
import { Menu, Moon, Sun, ArrowDown, ArrowUp, ShieldCheck } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useAuth } from '@/hooks/useAuth';
import { formatMbps } from '@/utils/formatters';

interface HeaderProps {
  onMenuToggle?: () => void;
  downloadSpeed?: number;
  uploadSpeed?: number;
}

export const Header: React.FC<HeaderProps> = ({
  onMenuToggle,
  downloadSpeed = 0,
  uploadSpeed = 0,
}) => {
  const { theme, toggleTheme } = useTheme();
  const { user } = useAuth();

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 md:px-8 flex items-center justify-between z-30">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="md:hidden p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Gateway connection badge */}
        <div className="flex items-center gap-2 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 px-3 py-1.5 rounded-full">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">
            Gateway: 192.168.16.2
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Live bandwidth chips */}
        <div className="hidden sm:flex items-center gap-3 bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 px-3 py-1.5 rounded-xl text-xs font-semibold">
          <div className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <ArrowDown className="w-3.5 h-3.5" />
            <span>{formatMbps(downloadSpeed)}</span>
          </div>
          <span className="text-slate-300 dark:text-slate-600">|</span>
          <div className="flex items-center gap-1 text-sky-600 dark:text-sky-400">
            <ArrowUp className="w-3.5 h-3.5" />
            <span>{formatMbps(uploadSpeed)}</span>
          </div>
        </div>

        {/* Theme switcher */}
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>

        {/* Security / Admin Badge */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-200 dark:border-slate-800">
          <div className="w-8 h-8 rounded-full bg-slate-900 text-white dark:bg-brand-600 flex items-center justify-center font-bold text-xs uppercase shadow-sm">
            {user?.username?.substring(0, 2) || 'AD'}
          </div>
        </div>
      </div>
    </header>
  );
};

