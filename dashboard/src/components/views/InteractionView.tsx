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
import { TrendingUp, MessageSquare } from 'lucide-react';

export default function InteractionView({ data, theme = 'dark' }: { data: InsightsData, theme?: 'dark' | 'light' }) {
  // Placeholder interaction history
  const history = [
    { id: 1, user: "Người dùng", bot: "Bot AI", message: "Phân tích sự kiện giáo dục mới nhất", response: "Đã trích xuất 5 sự kiện nổi bật, bao gồm vụ hủy kết quả thi KHKT.", time: "2 phút trước" },
    { id: 2, user: "Người dùng", bot: "Bot AI", message: "Tổng hợp drama showbiz tuần qua", response: "Đã tổng hợp 12 bài viết về nghệ sĩ A, xu hướng tiêu cực chiếm 60%.", time: "15 phút trước" },
    { id: 3, user: "Hệ thống", bot: "Cron Job", message: "Cập nhật dữ liệu tự động", response: "Hoàn thành cào dữ liệu từ 52 group Facebook giáo dục.", time: "1 giờ trước" },
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interaction History Card */}
        <div className="lg:col-span-2 p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl">
          <div className="flex items-center gap-2 mb-8">
            <MessageSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Lịch sử Tương tác (Bot AI)</h3>
          </div>
          
          <div className="space-y-4">
            {history.map((item) => (
              <div key={item.id} className="p-4 border border-zinc-100 dark:border-zinc-800 rounded-2xl bg-zinc-50/50 dark:bg-zinc-950/20 hover:border-blue-500/30 transition-all">
                <div className="flex justify-between items-center mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 text-[10px] font-bold rounded-lg uppercase">{item.user}</span>
                    <span className="text-zinc-400">→</span>
                    <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-[10px] font-bold rounded-lg uppercase">{item.bot}</span>
                  </div>
                  <span className="text-[10px] font-mono text-zinc-400 font-bold">{item.time}</span>
                </div>
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">" {item.message} "</p>
                  <p className="text-sm text-zinc-800 dark:text-zinc-200 font-medium">● {item.response}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-zinc-100 dark:border-zinc-800 flex justify-center">
             <p className="text-[10px] text-zinc-400 font-mono uppercase tracking-widest font-bold">Waiting for real-time history stream...</p>
          </div>
        </div>

        {/* Sidebar Status */}
        <div className="space-y-6">
           <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-lg relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4">
                 <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <h4 className="text-zinc-400 dark:text-zinc-500 text-[10px] font-mono tracking-tighter uppercase mb-4 font-bold">Bot Status</h4>
              <div className="space-y-4">
                 <div>
                    <p className="text-[10px] text-zinc-400 uppercase font-bold mb-1">AI Model</p>
                    <p className="text-sm font-black text-zinc-900 dark:text-white">GPT-4o / Analysis Optimized</p>
                 </div>
                 <div>
                    <p className="text-[10px] text-zinc-400 uppercase font-bold mb-1">Phản hồi trung bình</p>
                    <p className="text-sm font-black text-zinc-900 dark:text-white">1.2s</p>
                 </div>
                 <div>
                    <p className="text-[10px] text-zinc-400 uppercase font-bold mb-1">Queue Length</p>
                    <p className="text-sm font-black text-zinc-900 dark:text-white">0 tasks</p>
                 </div>
              </div>
           </div>

           <div className="p-6 bg-gradient-to-br from-blue-600 to-indigo-700 dark:from-zinc-800 dark:to-zinc-900 rounded-3xl text-white shadow-xl">
              <TrendingUp className="w-8 h-8 mb-4 opacity-50" />
              <h4 className="text-xs font-bold mb-2 uppercase opacity-80">Ghi chú</h4>
              <p className="text-[11px] leading-relaxed opacity-90 italic">"Hệ thống đang tích hợp Webhook từ Zalo/Telegram để hiển thị luồng hội thoại trực tiếp giữa Agent và ban quản trị."</p>
           </div>
        </div>
      </div>
    </div>
  );
}
