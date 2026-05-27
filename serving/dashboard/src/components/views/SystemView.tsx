import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell,
  Legend
} from 'recharts';
import { InsightsData } from '../../types';
import { Activity, Zap, ShieldCheck } from 'lucide-react';

export default function SystemView({ data, theme = 'dark' }: { data: InsightsData, theme?: 'dark' | 'light' }) {
  const stats = data?.overall?.total_comments;
  
  const chartData = [
    { name: 'Dữ liệu thô (Raw)', value: stats?.raw ?? 0, fill: '#52525b' },
    { name: 'Dữ liệu sạch (Clean)', value: stats?.clean ?? 0, fill: '#10b981' },
    { name: 'Dữ liệu rác (Trash)', value: stats?.trash ?? 0, fill: '#ef4444' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Metric Card 1 */}
        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl relative overflow-hidden group shadow-lg">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Zap className="w-16 h-16 text-yellow-500" />
          </div>
          <h4 className="text-zinc-400 dark:text-zinc-500 text-[10px] font-mono tracking-widest uppercase mb-2 font-bold">Trash Rate</h4>
          <p className="text-4xl font-black text-zinc-900 dark:text-white font-mono">{stats?.trash_rate ?? "0%"}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">Tỷ lệ rác trung bình trên toàn hệ thống.</p>
        </div>

        {/* Metric Card 2 */}
        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl relative overflow-hidden group shadow-lg">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Activity className="w-16 h-16 text-blue-500" />
          </div>
          <h4 className="text-zinc-400 dark:text-zinc-500 text-[10px] font-mono tracking-widest uppercase mb-2 font-bold">Live Web Research</h4>
          <p className="text-4xl font-black text-zinc-900 dark:text-white font-mono">14%</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">Tỷ lệ kích hoạt cào dữ liệu thời gian thực.</p>
        </div>

        {/* Metric Card 3 */}
        <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl relative overflow-hidden group shadow-lg">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <ShieldCheck className="w-16 h-16 text-emerald-500" />
          </div>
          <h4 className="text-zinc-400 dark:text-zinc-500 text-[10px] font-mono tracking-widest uppercase mb-2 font-bold">Events Analyzed</h4>
          <p className="text-4xl font-black text-zinc-900 dark:text-white font-mono">{data?.overall?.total_events_with_analysis ?? 0}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">Số sự kiện đã hoàn thành chu kỳ phân tích sâu.</p>
        </div>
      </div>

      <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl">
        <h3 className="text-xl font-bold text-zinc-900 dark:text-white mb-8">Pipeline Filtering Efficiency</h3>
        <div className="h-80 w-full font-mono">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#27272a' : '#e4e4e7'} vertical={false} />
              <XAxis dataKey="name" stroke={theme === 'dark' ? '#71717a' : '#71717a'} fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke={theme === 'dark' ? '#71717a' : '#71717a'} fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip 
                cursor={{ fill: theme === 'dark' ? '#27272a' : '#f4f4f5', opacity: 0.4 }}
                contentStyle={{ 
                  backgroundColor: theme === 'dark' ? '#18181b' : '#ffffff', 
                  border: theme === 'dark' ? '1px solid #3f3f46' : '1px solid #e4e4e7', 
                  borderRadius: '12px',
                  boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                }}
                itemStyle={{ fontSize: '12px', fontWeight: 600, color: theme === 'dark' ? '#ffffff' : '#18181b' }}
                labelStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontWeight: 'bold' }}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-center text-xs text-zinc-500 italic mt-4 font-medium">Hiệu suất lọc bình luận rác (Trash) vs bình luận sạch (Clean) qua n8n + Gemini Core.</p>
      </div>
    </div>
  );
}
