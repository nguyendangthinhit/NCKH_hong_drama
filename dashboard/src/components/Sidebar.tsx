import React, { useState } from 'react';
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
    { id: 'overview' as const, label: 'Tổng quan (Raw)', icon: LayoutDashboard },
    { id: 'sentiment' as const, label: 'Dư luận (Processed)', icon: ShieldAlert },
    { id: 'interaction' as const, label: 'Tương tác (Bot)', icon: MessageSquare },
    { id: 'system' as const, label: 'Hệ thống (Performance)', icon: Activity },
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
        "fixed inset-y-0 left-0 z-40 w-64 bg-zinc-50 dark:bg-zinc-950 border-r border-zinc-200 dark:border-zinc-800 transition-all duration-300 transform lg:translate-x-0 shadow-2xl",
        !isOpen && "-translate-x-full"
      )}>
        <div className="flex flex-col h-full p-6">
          <div className="mb-10">
            <h1 className="text-xl font-black bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-500 bg-clip-text text-transparent italic">
              DRAMA INTEL
            </h1>
            <p className="text-[10px] text-zinc-400 dark:text-zinc-500 tracking-widest uppercase mt-1 font-bold">Intelligence System</p>
          </div>

          <nav className="flex-1 space-y-1">
            {menuItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={cn(
                  "w-full flex items-center justify-between p-3 rounded-xl transition-all duration-200 group",
                  activeTab === item.id 
                    ? "bg-blue-600 dark:bg-blue-500/10 text-white dark:text-blue-400 shadow-lg shadow-blue-500/20" 
                    : "text-zinc-500 dark:text-zinc-500 hover:bg-white dark:hover:bg-zinc-900 hover:text-blue-600 dark:hover:text-zinc-300"
                )}
              >
                <div className="flex items-center gap-3">
                  <item.icon className={cn("w-5 h-5 transition-transform group-hover:scale-110", activeTab === item.id ? "animate-pulse" : "")} />
                  <span className="text-sm font-bold tracking-tight">{item.label}</span>
                </div>
                {activeTab === item.id && <ChevronRight className="w-4 h-4" />}
              </button>
            ))}
          </nav>

          <div className="mt-auto space-y-4 pt-6 border-t border-zinc-200 dark:border-zinc-800">
            <button 
              onClick={toggleTheme}
              className="w-full flex items-center gap-3 p-3 text-zinc-500 dark:text-zinc-500 hover:bg-white dark:hover:bg-zinc-900 rounded-xl transition-all group border border-transparent hover:border-zinc-200 dark:hover:border-zinc-800"
            >
              <div className="w-8 h-8 rounded-lg bg-zinc-100 dark:bg-zinc-900 flex items-center justify-center group-hover:rotate-12 transition-transform">
                {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-500" /> : <Moon className="w-4 h-4 text-indigo-400" />}
              </div>
              <div className="text-left">
                <p className="text-[11px] font-bold text-zinc-900 dark:text-zinc-300 line-clamp-1">
                  Chuyển sang {theme === 'light' ? 'Tối' : 'Sáng'}
                </p>
                <p className="text-[9px] text-zinc-400 dark:text-zinc-500 font-mono tracking-tighter">Theme Settings</p>
              </div>
              <Settings className="w-4 h-4 ml-auto group-hover:rotate-90 transition-transform text-zinc-400" />
            </button>

            <div className="p-4 bg-white dark:bg-zinc-900/50 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                <span className="text-[10px] font-mono text-zinc-500 dark:text-zinc-400 uppercase tracking-tighter font-bold">System Live</span>
              </div>
              <p className="text-[11px] text-zinc-400 dark:text-zinc-500 italic font-medium">Synced with External DB</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
