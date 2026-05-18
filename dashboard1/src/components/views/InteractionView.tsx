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
import { TrendingUp, MessageSquare, RefreshCcw, Star } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { GoogleGenAI } from '@google/genai';

const HISTORY_URL = 'https://raw.githubusercontent.com/nguyendangthinhit/NCKH_hong_drama/main/history.json';

export default function InteractionView({ data, theme = 'dark' }: { data: InsightsData, theme?: 'dark' | 'light' }) {
  const [history, setHistory] = useState<any[]>([]);
  const [apiKeys, setApiKeys] = useState<string[]>([]);
  const [currentKeyIndex, setCurrentKeyIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [topEvents, setTopEvents] = useState<string>('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const historyRef = useRef<any[]>([]);

  useEffect(() => {
    // Load API keys from public file
    const fetchApiKeys = async () => {
      try {
        const timestamp = new Date().getTime();
        const res = await fetch(`/api.txt?t=${timestamp}`);
        if (!res.ok) throw new Error("Failed to load API keys");
        const text = await res.text();
        const keys = text.split('\n').map(k => k.trim()).filter(k => k.length > 0);
        if (keys.length > 0) {
          setApiKeys(keys);
        } else {
          console.error("No API keys found in api.txt");
        }
      } catch (err) {
        console.error("Error loading API keys:", err);
      }
    };
    
    fetchApiKeys();

    const fetchHistory = async () => {
      try {
        setIsLoading(true);
        setErrorMsg('');
        const timestamp = new Date().getTime();
        const res = await fetch(`${HISTORY_URL}?t=${timestamp}`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        
        const rawText = await res.text();
        let data = [];
        try {
          data = JSON.parse(rawText);
        } catch (e: any) {
          throw new Error(`Dữ liệu JSON đang tải bị lỗi (Github cache). Đang chờ đồng bộ... Chi tiết: ${e.message}`);
        }

        // Filter out empty questions and map to display format
        const validHistory = data
          .filter((item: any) => item.question)
          .map((item: any, index: number) => ({
            id: index,
            user: 'NGƯỜI DÙNG',
            bot: 'BOT AI',
            message: item.question,
            response: item.answer,
            time: new Date(item.timestamp).toLocaleString()
          }));
        
        const newHistory = validHistory.reverse();
        
        // Only update state and re-analyze if new messages arrived
        if (newHistory.length !== historyRef.current.length || history.length === 0) {
          historyRef.current = newHistory;
          setHistory(newHistory);
          analyzeTopEvents(newHistory);
        }
      } catch (error: any) {
        console.error("Failed to fetch history:", error);
        setErrorMsg(error.message || 'Lỗi khi tải dữ liệu.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
    const intervalId = setInterval(fetchHistory, 30000);
    return () => clearInterval(intervalId);
  }, []);

  const analyzeTopEvents = async (historyData: any[]) => {
    // Wait until keys are loaded or give up if empty
    if (historyData.length === 0) return;
    
    setIsAnalyzing(true);
    try {
      const questions = historyData.map((h: any) => h.message).join('\n');
      const prompt = `Dưới đây là danh sách các câu hỏi của người dùng:\n${questions}\n\nHãy phân tích và tổng hợp thành danh sách Top 5 sự kiện/chủ đề được hỏi nhiều nhất.\nLưu ý quan trọng: KHÔNG TÍNH các câu hỏi xã giao, chào hỏi (ví dụ: hello, hi, chào bạn...).\nChỉ tập trung vào các sự kiện, drama hoặc nội dung cụ thể.\nTrả về định dạng danh sách rút gọn, ngắn gọn (chỉ gồm các gạch đầu dòng, không giải thích dài dòng).`;
      
      let attempt = 0;
      let success = false;
      let lastError = null;

      // Ensure we have keys to use
      let availableKeys = [...apiKeys];
      let startIndex = currentKeyIndex;
      
      // If component loaded fast and keys haven't loaded yet from useEffect, do an emergency fallback fetch
      if (availableKeys.length === 0) {
        try {
          const res = await fetch(`/api.txt?t=${new Date().getTime()}`);
          const text = await res.text();
          availableKeys = text.split('\n').map(k => k.trim()).filter(k => k.length > 0);
          if (availableKeys.length > 0) setApiKeys(availableKeys);
        } catch (e) {
          console.error("Could not fetch fallback keys");
        }
      }

      if (availableKeys.length === 0) {
        setTopEvents('Không tìm thấy API Key nào trong cấu hình.');
        return;
      }

      // Try rotating through keys until one works
      while (attempt < availableKeys.length && !success) {
        const keyToUse = availableKeys[(startIndex + attempt) % availableKeys.length];
        
        try {
          const ai = new GoogleGenAI({ apiKey: keyToUse });
          const response = await ai.models.generateContent({
              model: 'gemini-2.5-flash',
              contents: prompt,
          });
          setTopEvents(response.text || 'Không có kết quả.');
          success = true;
          
          // Update the current working index so next time we use it first
          if (attempt > 0) {
            setCurrentKeyIndex((startIndex + attempt) % availableKeys.length);
          }
        } catch (error) {
          console.error(`Gemini API call failed with key index ${(startIndex + attempt) % availableKeys.length}:`, error);
          lastError = error;
          attempt++;
        }
      }

      if (!success) {
        setTopEvents(`Lỗi phân tích: Đã thử toàn bộ ${availableKeys.length} API keys nhưng đều thất bại.`);
      }
    } catch (err) {
      console.error("Unexpected error in analyzeTopEvents:", err);
      setTopEvents('Lỗi hệ thống khi phân tích dữ liệu.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interaction History Card */}
        <div className="lg:col-span-2 p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl flex flex-col max-h-[700px]">
          <div className="flex items-center justify-between mb-8 shrink-0">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Lịch sử Tương tác (Bot AI)</h3>
            </div>
            {isLoading && <RefreshCcw className="w-4 h-4 text-zinc-400 animate-spin" />}
          </div>
          
          <div className="space-y-4 overflow-y-auto flex-1 pr-2 custom-scrollbar">
            {history.length > 0 ? history.map((item) => (
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
            )) : (
              <div className="h-full flex flex-col items-center justify-center">
                 <p className="text-zinc-400 text-sm italic">{errorMsg ? `Lỗi: ${errorMsg}` : 'Không có dữ liệu lịch sử.'}</p>
              </div>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-zinc-100 dark:border-zinc-800 flex justify-center shrink-0">
             <p className="text-[10px] text-zinc-400 font-mono uppercase tracking-widest font-bold">Dữ liệu đồng bộ từ Github (history.json) • Auto-sync 30s</p>
          </div>
        </div>

        {/* Sidebar Status */}
        <div className="space-y-6">
           <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-lg relative overflow-hidden flex flex-col h-full min-h-[300px]">
              <div className="absolute top-0 right-0 p-4">
                 <Star className="w-6 h-6 text-yellow-500/20" />
              </div>
              <h4 className="text-zinc-400 dark:text-zinc-500 text-[10px] font-mono tracking-tighter uppercase mb-4 font-bold">Top 5 Sự kiện Quan tâm (AI Analysis)</h4>
              
              <div className="mt-2 prose prose-sm dark:prose-invert max-w-none text-zinc-800 dark:text-zinc-300 flex-1">
                {isAnalyzing ? (
                  <div className="flex items-center gap-2 text-zinc-500 text-sm h-full justify-center">
                    <RefreshCcw className="w-4 h-4 animate-spin" /> Đang phân tích...
                  </div>
                ) : (
                   <div className="whitespace-pre-line text-sm leading-relaxed font-medium bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-2xl border border-zinc-100 dark:border-zinc-800/50 h-full">
                     {topEvents}
                   </div>
                )}
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
