/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar, { TabType } from './components/Sidebar';
import { Users, Globe, RefreshCcw } from 'lucide-react';

import OverviewView from './components/views/OverviewView';
import SentimentView from './components/views/SentimentView';
import InteractionView from './components/views/InteractionView';
import SystemView from './components/views/SystemView';
import { INSIGHTS_DATA as FALLBACK_DATA } from './constants';
import { InsightsData } from './types';

const INSIGHTS_URL = 'https://raw.githubusercontent.com/nguyendangthinhit/NCKH_hong_drama/main/data/insights.json';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [data, setData] = useState<InsightsData>(FALLBACK_DATA);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  useEffect(() => {
    // Apply theme on state change
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.classList.toggle('light', theme === 'light');
    document.documentElement.style.colorScheme = theme;
    
    // Persist preference
    localStorage.setItem('drama-theme', theme);
  }, [theme]);

  // Load persisted theme on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('drama-theme') as 'dark' | 'light';
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const fetchData = useCallback(async (isAuto = false) => {
    if (!isAuto) setIsLoading(true);
    setIsRefreshing(true);
    try {
      const response = await fetch(INSIGHTS_URL, { cache: 'no-store' });
      if (!response.ok) throw new Error('Failed to fetch insights data');
      const jsonData = await response.json();
      setData(jsonData);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error fetching data:', error);
      // Fallback to initial data if fetch fails
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      fetchData(true);
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-sans selection:bg-blue-500/30 transition-colors duration-300">
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        theme={theme} 
        toggleTheme={toggleTheme} 
      />
      
      <main className="lg:pl-64 transition-all duration-300">
        <div className="p-4 lg:p-8 max-w-7xl mx-auto">
          {/* Header Section */}
          <header className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-8">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white italic font-serif">
                  {activeTab === 'overview' && 'Hiệu suất thu thập'}
                  {activeTab === 'sentiment' && 'Insight Dư luận'}
                  {activeTab === 'interaction' && 'Hành vi Tương tác'}
                  {activeTab === 'system' && 'Trạng thái Hệ thống'}
                </h2>
                {isRefreshing && <RefreshCcw className="w-5 h-5 text-blue-500 animate-spin" />}
              </div>
              <p className="text-zinc-500 text-sm flex items-center gap-2">
                Cập nhật tự động (30s). Lần cuối: {lastUpdated.toLocaleTimeString()}
              </p>
            </div>
            
            <div className="flex items-center gap-6 px-6 py-3 bg-zinc-50 dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-xl">
              <StatItem 
                label="Tổng bản ghi" 
                value={data?.overall?.total_comments?.raw?.toLocaleString() ?? "0"} 
                icon={<Globe className="w-4 h-4 text-blue-500 dark:text-blue-400" />} 
              />
              <div className="w-px h-8 bg-zinc-200 dark:bg-zinc-800" />
              <StatItem 
                label="Links verify" 
                value={data?.overall?.total_links?.toString() ?? "0"} 
                icon={<Users className="w-4 h-4 text-purple-500 dark:text-purple-400" />} 
              />
            </div>
          </header>

          {/* Dynamic Content Area */}
          <div className="grid grid-cols-1 gap-6">
             {isLoading ? (
               <div className="h-96 flex flex-col items-center justify-center">
                 <RefreshCcw className="w-10 h-10 text-blue-500 animate-spin mb-4" />
                 <p className="text-zinc-500 font-mono text-sm tracking-widest uppercase">Loading fresh intelligence...</p>
               </div>
             ) : (
               <>
                 {activeTab === 'overview' && <OverviewView data={data} theme={theme} />}
                 {activeTab === 'sentiment' && <SentimentView data={data} theme={theme} />}
                 {activeTab === 'interaction' && <InteractionView data={data} theme={theme} />}
                 {activeTab === 'system' && <SystemView data={data} theme={theme} />}
               </>
             )}
          </div>
        </div>
      </main>
    </div>
  );
}

function StatItem({ label, value, icon }: { label: string, value: string, icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <div className="hidden sm:block">{icon}</div>
      <div>
        <p className="text-[10px] text-zinc-500 dark:text-zinc-500 uppercase tracking-wider font-semibold">{label}</p>
        <p className="text-lg font-bold text-zinc-900 dark:text-white font-mono">{value}</p>
      </div>
    </div>
  );
}
