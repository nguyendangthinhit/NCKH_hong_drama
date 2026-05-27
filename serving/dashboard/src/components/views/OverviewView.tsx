import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';
import { InsightsData } from '../../types';

export default function OverviewView({ data, theme = 'dark' }: { data: InsightsData, theme?: 'dark' | 'light' }) {
  const overall = data?.overall;

  const categoryChartData = [
    { name: 'Giáo dục', value: overall?.by_category?.education?.events ?? 0, color: '#3b82f6' },
    { name: 'Showbiz', value: overall?.by_category?.showbiz?.events ?? 0, color: '#9333ea' }
  ];

  const sourceChartData = [
    { name: 'Website', value: overall?.total_links_website ?? 0, color: '#f59e0b' },
    { name: 'Facebook', value: overall?.total_links_facebook ?? 0, color: '#8b5cf6' }
  ];
  
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Scorecards */}
        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl relative overflow-hidden">
          <div className="absolute -right-4 -bottom-4 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl" />
          <h3 className="text-zinc-500 dark:text-zinc-500 text-xs font-mono uppercase tracking-widest mb-4 font-bold">Tổng số bản ghi (Tầng 1)</h3>
          <div className="flex items-baseline gap-2">
            <span className="text-5xl font-black text-zinc-900 dark:text-white font-mono">{overall?.total_comments?.raw?.toLocaleString() ?? "0"}</span>
            <span className="text-emerald-500 text-sm font-bold">Comments</span>
          </div>
          <div className="mt-8 flex items-center justify-between text-[10px] font-mono text-zinc-400 dark:text-zinc-500 font-bold uppercase">
             <span>Lọc sạch: {overall?.total_comments?.clean?.toLocaleString() ?? "0"}</span>
             <span>Rác: {overall?.total_comments?.trash?.toLocaleString() ?? "0"}</span>
          </div>
          <div className="mt-2 flex gap-1 h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
             <div className="bg-blue-600 dark:bg-blue-500 transition-all duration-1000" style={{ width: `${overall?.total_comments?.raw ? (overall.total_comments.clean / overall.total_comments.raw) * 100 : 0}%` }} />
             <div className="bg-red-600 dark:bg-red-500 transition-all duration-1000" style={{ width: `${overall?.total_comments?.raw ? (overall.total_comments.trash / overall.total_comments.raw) * 100 : 0}%` }} />
          </div>
        </div>

        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl relative overflow-hidden">
          <div className="absolute -right-4 -top-4 w-32 h-32 bg-amber-500/10 rounded-full blur-3xl" />
          <h3 className="text-zinc-500 dark:text-zinc-500 text-xs font-mono uppercase tracking-widest mb-4 font-bold">Phân bổ Tài nguyên</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase font-mono mb-1 font-bold">Sự kiện</p>
              <p className="text-2xl font-black text-zinc-900 dark:text-white font-mono">{overall?.total_events ?? 0}</p>
              <div className="mt-2 space-y-1">
                <div className="flex justify-between text-[10px] font-mono font-bold">
                  <span className="text-emerald-600 dark:text-emerald-500">Phân tích:</span>
                  <span className="text-zinc-700 dark:text-white">{overall?.total_events_with_analysis ?? 0}</span>
                </div>
                <div className="flex justify-between text-[10px] font-mono font-bold">
                  <span className="text-amber-500">Chờ:</span>
                  <span className="text-zinc-700 dark:text-white">{overall?.total_events_without_analysis ?? 0}</span>
                </div>
              </div>
            </div>
            <div>
              <p className="text-[10px] text-zinc-400 dark:text-zinc-500 uppercase font-mono mb-1 font-bold">Links</p>
              <p className="text-2xl font-black text-zinc-900 dark:text-white font-mono">{overall?.total_links ?? 0}</p>
              <div className="mt-2 space-y-1">
                <div className="flex justify-between text-[10px] font-mono font-bold">
                  <span className="text-blue-600 dark:text-blue-400">Website:</span>
                  <span className="text-zinc-700 dark:text-white">{overall?.total_links_website ?? 0}</span>
                </div>
                <div className="flex justify-between text-[10px] font-mono font-bold">
                  <span className="text-purple-600 dark:text-purple-400">Facebook:</span>
                  <span className="text-zinc-700 dark:text-white">{overall?.total_links_facebook ?? 0}</span>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-6 h-2 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden flex">
            <div className="bg-emerald-600 dark:bg-emerald-500 h-full transition-all duration-1000" style={{ width: `${overall?.total_events ? ((overall.total_events_with_analysis || 0) / overall.total_events) * 100 : 0}%` }} title="Events Analyzed" />
            <div className="bg-amber-500 h-full transition-all duration-1000" style={{ width: `${overall?.total_events ? ((overall.total_events_without_analysis || 0) / overall.total_events) * 100 : 0}%` }} title="Pending Analysis" />
          </div>
        </div>
      </div>

      {/* Horizontal Bar Charts Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-4 bg-blue-500 rounded-full" />
            <h3 className="text-zinc-900 dark:text-zinc-100 text-sm font-black uppercase tracking-wider">Hiệu suất theo Lĩnh vực (Events)</h3>
          </div>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryChartData} layout="vertical" margin={{ left: 10, right: 30, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#27272a' : '#e4e4e7'} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  stroke={theme === 'dark' ? '#d4d4d8' : '#71717a'} 
                  fontSize={11} 
                  tickLine={false} 
                  axisLine={false}
                  width={100}
                />
                <Tooltip 
                  cursor={{ fill: theme === 'dark' ? '#27272a' : '#f4f4f5', opacity: 0.4 }}
                  contentStyle={{ 
                    backgroundColor: theme === 'dark' ? '#18181b' : '#ffffff', 
                    border: theme === 'dark' ? '1px solid #3f3f46' : '1px solid #e4e4e7', 
                    borderRadius: '12px',
                    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                  }}
                  itemStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontSize: '12px', fontWeight: 600 }}
                  labelStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontWeight: 'bold' }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={24}>
                  {categoryChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex justify-around items-center">
            {categoryChartData.map(item => (
              <div key={item.name} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-[10px] font-bold text-zinc-500 dark:text-zinc-400 font-mono">{item.name}: {item.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-4 bg-amber-500 rounded-full" />
            <h3 className="text-zinc-900 dark:text-zinc-100 text-sm font-black uppercase tracking-wider">Tỷ trọng Nguồn cào (Links)</h3>
          </div>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceChartData} layout="vertical" margin={{ left: 10, right: 30, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#27272a' : '#e4e4e7'} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  stroke={theme === 'dark' ? '#d4d4d8' : '#71717a'} 
                  fontSize={11} 
                  tickLine={false} 
                  axisLine={false}
                  width={100}
                />
                <Tooltip 
                  cursor={{ fill: theme === 'dark' ? '#27272a' : '#f4f4f5', opacity: 0.4 }}
                  contentStyle={{ 
                    backgroundColor: theme === 'dark' ? '#18181b' : '#ffffff', 
                    border: theme === 'dark' ? '1px solid #3f3f46' : '1px solid #e4e4e7', 
                    borderRadius: '12px',
                    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                  }}
                  itemStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontSize: '12px', fontWeight: 600 }}
                  labelStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontWeight: 'bold' }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={24}>
                  {sourceChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex justify-around items-center">
            {sourceChartData.map(item => (
              <div key={item.name} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-[10px] font-bold text-zinc-500 dark:text-zinc-400 font-mono">{item.name}: {item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
         <CategoryCard 
            title="Giáo dục (Education)" 
            events={data?.overall?.by_category?.education?.events ?? 0} 
            comments={data?.overall?.by_category?.education?.comments_clean ?? 0}
            color="border-blue-500/20 bg-blue-500/5 text-blue-700 dark:text-blue-300"
         />
         <CategoryCard 
            title="Showbiz / Giải trí" 
            events={data?.overall?.by_category?.showbiz?.events ?? 0} 
            comments={data?.overall?.by_category?.showbiz?.comments_clean ?? 0}
            color="border-purple-500/20 bg-purple-500/5 text-purple-700 dark:text-purple-300"
         />
      </div>
    </div>
  );
}

function CategoryCard({ title, events, comments, color }: { title: string, events: number, comments: number, color: string }) {
    return (
        <div className={`p-6 border rounded-3xl flex flex-col justify-between shadow-sm transition-all hover:scale-[1.02] ${color}`}>
            <h4 className="text-sm font-black">{title}</h4>
            <div className="mt-4 flex items-end gap-6">
                <div>
                    <p className="text-[10px] opacity-70 uppercase tracking-tighter font-bold">Sự kiện</p>
                    <p className="text-2xl font-black font-mono">{events}</p>
                </div>
                <div>
                    <p className="text-[10px] opacity-70 uppercase tracking-tighter font-bold">Clean Comments</p>
                    <p className="text-2xl font-black font-mono">{comments.toLocaleString()}</p>
                </div>
            </div>
        </div>
    )
}
