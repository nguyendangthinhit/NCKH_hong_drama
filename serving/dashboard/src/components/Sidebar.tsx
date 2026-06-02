import React, { useState } from 'react';
import { motion } from 'motion/react';
import {
  LayoutDashboard,
  MessageSquare,
  TrendingUp,
  BarChart3,
  ShieldAlert,
  Activity,
  ChevronRight,
  Menu,
  X,
  Settings,
  Sun,
  Moon
} from 'lucide-react';
import { cn } from '../lib/utils';

export type TabType = 'overview' | 'sentiment' | 'interaction' | 'system';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export default function Sidebar({ activeTab, setActiveTab, theme, toggleTheme }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(true);

  const menuItems = [
    { id: 'overview' as const, label: 'Overview', sub: 'Hiệu suất thu thập', icon: LayoutDashboard },
    { id: 'sentiment' as const, label: 'Sentiment', sub: 'Insight dư luận', icon: ShieldAlert },
    { id: 'interaction' as const, label: 'Interaction', sub: 'Tương tác & bot', icon: MessageSquare },
    { id: 'system' as const, label: 'System', sub: 'Trạng thái pipeline', icon: Activity },
  ];

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-md shadow-lg"
      >
        {isOpen ? <X className="w-5 h-5 text-zinc-600 dark:text-zinc-400" /> : <Menu className="w-5 h-5 text-zinc-600 dark:text-zinc-400" />}
      </button>

      <div className={cn(
        "fixed inset-y-0 left-0 z-40 w-64 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-xl border-r border-zinc-200/70 dark:border-zinc-800/70 transition-all duration-300 transform lg:translate-x-0",
        !isOpen && "-translate-x-full"
      )}>
        <div className="flex flex-col h-full p-5">
          {/* Brand */}
          <div className="mb-8 px-2">
            <div className="flex items-center gap-2.5 mb-1">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Activity className="w-4 h-4 text-white" />
              </div>
              <div>
                <h1 className="text-base font-semibold tracking-tight text-zinc-900 dark:text-white leading-none">Drama Intel</h1>
                <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-1 tracking-wider">Sentiment intelligence</p>
              </div>
            </div>
          </div>

          {/* Section label */}
          <p className="px-3 mb-2 text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">Navigation</p>

          <nav className="flex-1 space-y-0.5">
            {menuItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <motion.button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  whileHover={{ x: isActive ? 0 : 2 }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl group relative",
                    isActive
                      ? "text-white dark:text-zinc-900"
                      : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-white"
                  )}
                >
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active-pill"
                      className="absolute inset-0 bg-zinc-900 dark:bg-white rounded-xl -z-10"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  )}
                  <item.icon className={cn(
                    "w-4 h-4 shrink-0 transition-colors",
                    isActive ? "text-white dark:text-zinc-900" : "text-zinc-400 dark:text-zinc-500 group-hover:text-zinc-700 dark:group-hover:text-zinc-200"
                  )} />
                  <div className="flex-1 text-left min-w-0">
                    <p className={cn("text-sm font-medium leading-tight truncate", isActive ? "" : "text-zinc-700 dark:text-zinc-300")}>{item.label}</p>
                    <p className={cn("text-[10px] mt-0.5 leading-tight truncate", isActive ? "text-white/70 dark:text-zinc-600" : "text-zinc-400 dark:text-zinc-500")}>{item.sub}</p>
                  </div>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 opacity-60" />}
                </motion.button>
              );
            })}
          </nav>

          <div className="mt-auto space-y-3 pt-5 border-t border-zinc-200/70 dark:border-zinc-800/70">
            <button
              onClick={toggleTheme}
              className="w-full flex items-center gap-3 px-3 py-2.5 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900 rounded-xl transition-all group"
            >
              <div className="w-7 h-7 rounded-lg bg-zinc-100 dark:bg-zinc-900 flex items-center justify-center group-hover:scale-105 transition-transform">
                {theme === 'light' ? <Sun className="w-3.5 h-3.5 text-amber-500" /> : <Moon className="w-3.5 h-3.5 text-indigo-400" />}
              </div>
              <div className="text-left flex-1 min-w-0">
                <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300 leading-tight">
                  {theme === 'light' ? 'Light mode' : 'Dark mode'}
                </p>
                <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-0.5">Click to toggle</p>
              </div>
              <Settings className="w-3.5 h-3.5 ml-auto opacity-0 group-hover:opacity-60 transition-opacity text-zinc-400" />
            </button>

            <div className="px-3 py-2.5 bg-zinc-50 dark:bg-zinc-900/50 rounded-xl border border-zinc-200/70 dark:border-zinc-800/70">
              <div className="flex items-center gap-2 mb-1">
                <span className="relative flex w-2 h-2">
                  <span className="absolute inline-flex w-full h-full rounded-full bg-emerald-400 opacity-75 animate-ping" />
                  <span className="relative inline-flex rounded-full w-2 h-2 bg-emerald-500" />
                </span>
                <span className="text-[10px] font-medium text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">System live</span>
              </div>
              <p className="text-[10px] text-zinc-400 dark:text-zinc-500">Synced · auto-refresh 30s</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
