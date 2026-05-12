import React, { useState, useEffect } from 'react';
import { 
  PieChart, 
  Pie, 
  Cell, 
  ResponsiveContainer, 
  Tooltip, 
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid
} from 'recharts';
import { InsightsData, StanceDistribution } from '../../types';
import { GraduationCap, Ticket, Activity, ChevronLeft, ExternalLink, MessageCircle, TrendingUp } from 'lucide-react';

const STANCE_COLORS: Record<string, string> = {
  // Vietnamese with underscores
  'tích_cực': '#10b981',
  'tiêu_cực': '#ef4444',
  'trung_lập': '#71717a',
  'ý_kiến_riêng': '#f59e0b',
  'tích_cực_hơn': '#34d399',
  'tiêu_cực_hơn': '#f87171',
  'rác': '#444444',

  // Vietnamese with spaces
  'tích cực': '#10b981',
  'tiêu cực': '#ef4444',
  'trung lập': '#71717a',
  'ý kiến riêng': '#f59e0b',
  'ý kiến': '#f59e0b',

  // Non-accented variants
  'tich_cuc': '#10b981',
  'tieu_cuc': '#ef4444',
  'trung_lap': '#71717a',
  'y_kien_rieng': '#f59e0b',
  'tich cuc': '#10b981',
  'tieu cuc': '#ef4444',
  'trung lap': '#71717a',
  'y kien rieng': '#f59e0b',
  'y kien': '#f59e0b',

  // Other types
  'đồng tình': '#10b981',
  'phản đối': '#ef4444',
  'tranh luận': '#f59e0b',
  'quan tâm': '#3b82f6',
  'hỏi đáp': '#8b5cf6',
};

const EMOTION_COLORS: Record<string, string> = {
  // Common with Stance
  'tích cực': '#10b981',
  'tiêu cực': '#ef4444',
  'trung lập': '#71717a',
  'ý kiến riêng': '#f59e0b',
  'tích_cực': '#10b981',
  'tiêu_cực': '#ef4444',
  'trung_lập': '#71717a',
  'ý_kiến_riêng': '#f59e0b',

  // Showbiz specific
  'phẫn nộ': '#ef4444',
  'phan_no': '#ef4444',
  'cà khịa': '#f59e0b',
  'ca_khia': '#f59e0b',
  'đồng cảm': '#3b82f6',
  'dong_cam': '#3b82f6',
  'ủng hộ': '#10b981',
  'ung_ho': '#10b981',
};

const GET_COLOR = (key: string, category: 'education' | 'showbiz') => {
  const k = key.toLowerCase().trim().replace(/_/g, ' ');
  
  const colors = category === 'education' ? STANCE_COLORS : EMOTION_COLORS;
  
  // 1. Exact match with spaces
  if (colors[k]) return colors[k];
  
  // 2. Exact match with underscores
  const keyWithUnderscores = k.replace(/ /g, '_');
  if (colors[keyWithUnderscores]) return colors[keyWithUnderscores];
  
  // 3. Stricter mapping for common terms
  if (k.includes('tiêu cực') || k.includes('tieu cuc')) return STANCE_COLORS['tiêu cực'];
  if (k.includes('tích cực') || k.includes('tich cuc')) return STANCE_COLORS['tích cực'];
  if (k.includes('trung lập') || k.includes('trung lap')) return STANCE_COLORS['trung lập'];
  if (k.includes('ý kiến') || k.includes('y kien') || k.includes('opinion')) return STANCE_COLORS['ý kiến riêng'];
  if (k.includes('rác') || k.includes('trash')) return STANCE_COLORS['rác'];
  
  // 4. Fallback to existing logic but prioritized
  const found = Object.keys(colors).find(s => k === s || k.startsWith(s) || s.startsWith(k));
  if (found) return colors[found];
  
  return '#8884d8';
};

const BASE_RAW_URL = "https://raw.githubusercontent.com/nguyendangthinhit/NCKH_hong_drama/main/data";

interface EventDetailData {
  id_content: string;
  event_name: string;
  total_comments: number;
  emotion_stats?: Record<string, number>;
  stance_stats?: Record<string, number>;
  stance_distribution?: Record<string, number>;
  top_comments?: {
    most_popular: any[];
  }
}

const LegendItem = ({ color, name, value, percent }: { color: string, name: string, value: number, percent: string }) => (
  <div className="p-4 bg-white dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-2xl flex items-center justify-between group hover:border-blue-500/30 dark:hover:border-zinc-700 transition-all shadow-sm">
    <div className="flex items-center gap-3">
      <div className="w-1.5 h-8 rounded-full" style={{ backgroundColor: color }} />
      <div>
        <p className="text-[10px] text-zinc-400 dark:text-zinc-500 font-bold uppercase tracking-tighter">{name}</p>
        <p className="text-xl font-black text-zinc-900 dark:text-white font-mono">{value.toLocaleString()}</p>
      </div>
    </div>
    <div className="text-right">
      <p className="text-lg font-black text-blue-600 dark:text-zinc-300 font-mono">{percent}</p>
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 italic">tổng cộng</p>
    </div>
  </div>
);

export default function SentimentView({ data, theme = 'dark' }: { data: InsightsData, theme?: 'dark' | 'light' }) {
  const [activeCategory, setActiveCategory] = useState<'education' | 'showbiz'>('education');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [eventDetail, setEventDetail] = useState<EventDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const categoryData = data?.[activeCategory];

  useEffect(() => {
    if (selectedEventId) {
      fetchEventDetail(selectedEventId);
    } else {
      setEventDetail(null);
    }
  }, [selectedEventId, activeCategory]);

  const fetchEventDetail = async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // Try preferred path first
      const folder = activeCategory === 'education' ? 'process_education/analyzed_dataa' : 'process_showbiz/analyzed_data';
      let url = `${BASE_RAW_URL}/${folder}/summary/${id}.json`;
      
      let response = await fetch(url);
      
      // Fallback for education if 'analyzed_dataa' fails
      if (!response.ok && activeCategory === 'education') {
        const fallbackUrl = `${BASE_RAW_URL}/process_education/analyzed_data/summary/${id}.json`;
        response = await fetch(fallbackUrl);
      }

      if (!response.ok) throw new Error(`Không thể tải dữ liệu chi tiết sự kiện (${id}).`);
      
      const json = await response.json();
      setEventDetail(json);
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err instanceof Error ? err.message : 'Đã xảy ra lỗi khi tải dữ liệu từ hệ thống.');
    } finally {
      setIsLoading(false);
    }
  };

  const currentDistribution: StanceDistribution = activeCategory === 'education' 
    ? categoryData?.stance_distribution ?? {} 
    : categoryData?.emotion_distribution ?? {};
  
  const getEventDistribution = (detail: any) => {
    if (!detail) return {};
    
    // 1. Try to find a stats/distribution object
    let dist: any = null;
    
    // Look for common stat keys across both categories to be safe
    const preferredKeys = [
      'comment_counts', 'analysis', 'stance_stats', 'stance_distribution', 
      'sentiment_stats', 'emotion_stats', 'emotion_distribution', 
      'sentiment_distribution', 'stance', 'emotion', 'sentiment', 'stats', 
      'distribution', 'thong_ke', 'phan_loai', 'opinion_stats'
    ];
    
    for (const key of preferredKeys) {
      if (detail[key] && typeof detail[key] === 'object' && Object.keys(detail[key]).length > 0) {
        // Special case: if it's 'analysis', we need to check if the children have a 'count' property
        if (key === 'analysis') {
          const children = Object.values(detail[key]);
          const hasCount = children.some((child: any) => child && typeof child === 'object' && 'count' in child);
          if (hasCount) {
            dist = detail[key];
            break;
          }
        } else {
          dist = detail[key];
          break;
        }
      }
    }
    
    // 2. If not found, try to find any key that looks like it contains stats
    if (!dist) {
      const possibleKey = Object.keys(detail).find(k => {
        const kl = k.toLowerCase().replace(/_/g, ' ');
        return (kl.includes('stance') || kl.includes('emotion') || kl.includes('sentiment') || 
                kl.includes('stats') || kl.includes('distribution') || kl.includes('thong_ke') || 
                kl.includes('phân loại') || kl.includes('ý kiến') || kl.includes('count')) &&
               typeof detail[k] === 'object';
      });
      dist = possibleKey ? detail[possibleKey] : detail;
    }

    const filteredDist: any = {};
    const keysToExclude = [
      'total', 'id_content', 'event_name', 'top_comments', 
      'controversial', 'toxic', 'threads', 'id', 'name', 'time_event', 'ten_su_kien', 
      'description', 'url', 'link', 'summary', 'keywords', 'conclusion', 'updated_at', 'created_at'
    ];

    // Helper to extract numeric value from various formats
    const getNumericValue = (v: any): number | null => {
      if (typeof v === 'number') return v;
      if (typeof v === 'string') {
        const cleaned = v.replace(/,/g, '').replace(/%/g, '').trim();
        const parsed = parseFloat(cleaned);
        return isNaN(parsed) ? null : parsed;
      }
      if (typeof v === 'object' && v !== null) {
        if ('count' in v && typeof v.count === 'number') return v.count;
        if ('count' in v && typeof v.count === 'string') return parseFloat(v.count.replace(/,/g, ''));
        if ('value' in v && typeof v.value === 'number') return v.value;
        if ('quantity' in v && typeof v.quantity === 'number') return v.quantity;
      }
      return null;
    };

    // If dist is an array (e.g. [{"label": "A", "value": 10}, ...])
    if (Array.isArray(dist)) {
      dist.forEach((item: any) => {
        if (typeof item === 'object' && item !== null) {
          const label = item.label || item.name || item.key || item.category || item.type || item.ten || item.phan_loai;
          const value = getNumericValue(item.value ?? item.count ?? item.quantity ?? item.total);
          if (label && typeof label === 'string' && value !== null) {
            filteredDist[label] = value;
          }
        }
      });
    } else if (typeof dist === 'object' && dist !== null) {
      // If dist is an object
      Object.entries(dist).forEach(([k, v]) => {
        const kl = k.toLowerCase().trim();
        // Clean key: replace underscores with spaces
        const label = k.replace(/_/g, ' ').trim();
        
        // Stricter exclusion: only exclude if the key EXACTLY matches an excluded key
        const shouldExclude = keysToExclude.some(ex => kl === ex);
        
        if (!shouldExclude) {
          const numVal = getNumericValue(v);
          if (numVal !== null) {
            filteredDist[label] = numVal;
          }
        }
      });
    }

    // 3. Last ditch effort: if we still have nothing, scan the whole detail for numeric fields
    if (Object.keys(filteredDist).length === 0) {
        Object.entries(detail).forEach(([k, v]) => {
            const kl = k.toLowerCase();
            const shouldExclude = keysToExclude.some(ex => kl === ex || kl.includes(ex));
            if (!shouldExclude) {
                const numVal = getNumericValue(v);
                if (numVal !== null && numVal > 0 && numVal < 1000000) { // arbitrary cap to avoid ID confusion
                    filteredDist[k] = numVal;
                }
            }
        });
    }

    return filteredDist;
  };

  const distributionToUse = eventDetail 
    ? getEventDistribution(eventDetail)
    : currentDistribution;

  const chartData = Object.entries(distributionToUse || {}).map(([key, value]) => {
    const count = typeof value === 'object' ? (value as any).count : (value as number);
    const total = eventDetail?.total_comments || 
                  Object.values(distributionToUse || {}).reduce((acc: number, cur: any) => {
                    const val = typeof cur === 'object' ? cur.count : cur;
                    return acc + (typeof val === 'number' ? val : 0);
                  }, 0) || 1;

    const percentValue = typeof value === 'object' ? (value as any).percent : (total > 0 ? `${Math.round((count / total) * 100)}%` : "0%");
    
    return {
      name: key.replace(/_/g, ' ').toUpperCase(),
      value: count ?? 0,
      percent: percentValue,
      color: GET_COLOR(key, activeCategory)
    };
  }).sort((a, b) => b.value - a.value);

  const hasData = chartData.some(item => item.value > 0);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Category Tabs and Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex p-1 bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl w-fit">
          <button 
            onClick={() => {
              setActiveCategory('education');
              setSelectedEventId(null);
            }}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${
              activeCategory === 'education' 
              ? 'bg-blue-600 text-white shadow-lg' 
              : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}
          >
            <GraduationCap className="w-4 h-4" />
            Giáo dục
          </button>
          <button 
            onClick={() => {
              setActiveCategory('showbiz');
              setSelectedEventId(null);
            }}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${
              activeCategory === 'showbiz' 
              ? 'bg-purple-600 text-white shadow-lg' 
              : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
            }`}
          >
            <Ticket className="w-4 h-4" />
            Showbiz
          </button>
        </div>

        {selectedEventId && (
          <button 
            onClick={() => setSelectedEventId(null)}
            className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 rounded-xl transition-colors text-sm font-medium border border-zinc-200 dark:border-zinc-700 shadow-sm"
          >
            <ChevronLeft className="w-4 h-4" />
            Quay lại Tổng thể
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Column */}
        <div className="lg:col-span-2 p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl relative">
          {isLoading && (
            <div className="absolute inset-0 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm z-50 flex flex-col items-center justify-center rounded-3xl">
              <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin mb-4" />
              <p className="text-zinc-500 dark:text-zinc-400 font-mono text-xs uppercase tracking-widest text-center">Đang phân tích dữ liệu...</p>
            </div>
          )}

          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold text-zinc-900 dark:text-white">
                {selectedEventId ? 'Phân tích Chi tiết Sự kiện' : `Thái độ Dư luận (${activeCategory === 'education' ? 'Giáo dục' : 'Showbiz'})`}
              </h3>
              <p className="text-zinc-400 dark:text-zinc-500 text-xs mt-1">
                {selectedEventId 
                  ? (eventDetail?.event_name || 'Đang tải tên sự kiện...') 
                  : `Dữ liệu phân tích từ ${categoryData?.comment_stats?.total_clean?.toLocaleString() ?? "0"} bình luận đã làm sạch.`
                }
              </p>
            </div>
          </div>

          <div className="h-80 w-full flex items-center justify-center">
            {error ? (
              <div className="text-center p-8">
                <p className="text-red-400 text-sm font-mono">{error}</p>
                <button 
                  onClick={() => selectedEventId && fetchEventDetail(selectedEventId)}
                  className="mt-4 px-4 py-2 bg-zinc-800 text-zinc-300 rounded-lg text-xs hover:bg-zinc-700"
                >
                  Thử lại
                </button>
              </div>
            ) : hasData ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    nameKey="name"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: theme === 'dark' ? '#18181b' : '#ffffff', 
                      border: theme === 'dark' ? '1px solid #3f3f46' : '1px solid #e4e4e7', 
                      borderRadius: '12px',
                      boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                    }}
                    itemStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontSize: '12px', fontWeight: 600 }}
                    labelStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontWeight: 'bold' }}
                  />
                  <Legend 
                    verticalAlign="bottom" 
                    height={36} 
                    iconType="circle"
                    payload={chartData.map(item => ({
                      value: item.name,
                      type: 'circle',
                      color: item.color
                    }))}
                    formatter={(value: string) => <span className="text-zinc-400 text-xs font-medium ml-2">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center">
                <div className="w-16 h-16 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto mb-4 border border-zinc-200 dark:border-zinc-700">
                  <Activity className="w-8 h-8 text-zinc-400 dark:text-zinc-600" />
                </div>
                <p className="text-zinc-400 dark:text-zinc-500 font-mono text-xs tracking-widest uppercase">Waiting for analysis...</p>
                <p className="text-zinc-400 dark:text-zinc-600 text-[10px] mt-1 italic">Chưa có dữ liệu dư luận cho chuyên mục này.</p>
              </div>
            )}
          </div>
        </div>

        {/* Legend/Stats Column */}
        <div className="space-y-4">
          {hasData ? (
            chartData.map((item) => (
              <LegendItem 
                key={item.name}
                color={item.color}
                name={item.name}
                value={item.value}
                percent={item.percent}
              />
            ))
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 bg-zinc-50 dark:bg-zinc-900/30 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl">
              <p className="text-zinc-400 dark:text-zinc-600 text-[10px] text-center font-mono uppercase font-bold">System Standby</p>
            </div>
          )}
        </div>
      </div>

      {/* Top Events Section (Only show if no event is selected) */}
      {!selectedEventId && (
        <div className="space-y-6">
          <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl overflow-hidden">
            <div className="flex items-center gap-2 mb-8">
              <TrendingUp className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Sự kiện Trending (by Query Volume)</h3>
            </div>
            
            <div className="h-80 w-full mb-10">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart 
                   data={(categoryData?.top_events_by_comments ?? [])
                      .sort((a: any, b: any) => (b.total || 0) - (a.total || 0))
                      .slice(0, 5)
                      .map((event: any) => ({
                        name: (event.ten_su_kien?.length ?? 0) > 40 ? event.ten_su_kien.substring(0, 40) + '...' : (event.ten_su_kien ?? "Unknown"),
                        total: event.total ?? 0
                   }))} 
                   layout="vertical" 
                   margin={{ left: 10, right: 30 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#27272a' : '#e4e4e7'} horizontal={false} />
                  <XAxis type="number" stroke={theme === 'dark' ? '#52525b' : '#71717a'} fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis 
                    dataKey="name" 
                    type="category" 
                    stroke={theme === 'dark' ? '#d4d4d8' : '#71717a'} 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false}
                    width={180}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: theme === 'dark' ? '#18181b' : '#ffffff', 
                      border: theme === 'dark' ? '1px solid #3f3f46' : '1px solid #e4e4e7', 
                      borderRadius: '12px',
                      boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                    }}
                    itemStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontSize: '12px' }}
                    labelStyle={{ color: theme === 'dark' ? '#ffffff' : '#18181b', fontWeight: 'bold' }}
                  />
                  <Bar dataKey="total" fill={activeCategory === 'education' ? '#3b82f6' : '#9333ea'} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <h3 className="text-xl font-bold text-zinc-900 dark:text-white mb-6 relative z-10">
              Danh sách chi tiết {activeCategory === 'education' ? 'Giáo dục' : 'Showbiz'}
            </h3>
            <div className="grid grid-cols-1 gap-4 relative z-10">
              {(categoryData?.top_events_by_comments ?? []).length > 0 ? (
                (categoryData?.top_events_by_comments ?? [])
                  .sort((a: any, b: any) => (b.total || 0) - (a.total || 0))
                  .slice(0, 5)
                  .map((event: any, index: number) => (
                  <div 
                    key={event.id_content} 
                    onClick={() => setSelectedEventId(event.id_content)}
                    className="p-5 bg-zinc-50 dark:bg-zinc-950/50 border border-zinc-200 dark:border-zinc-800 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-blue-500/50 hover:bg-white dark:hover:bg-zinc-900/50 transition-all group cursor-pointer shadow-sm"
                  >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`flex items-center justify-center w-6 h-6 rounded text-xs font-bold transition-colors ${
                        activeCategory === 'education' 
                        ? 'bg-blue-500/20 text-blue-600 dark:text-blue-400 group-hover:bg-blue-500 group-hover:text-white' 
                        : 'bg-purple-500/20 text-purple-600 dark:text-purple-400 group-hover:bg-purple-500 group-hover:text-white'
                      }`}>
                        #{index + 1}
                      </span>
                      <span className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500">ID: {event.id_content}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <h4 className={`text-sm font-bold text-zinc-900 dark:text-white leading-tight mb-1 transition-colors ${
                        activeCategory === 'education' ? 'group-hover:text-blue-700 dark:group-hover:text-blue-200' : 'group-hover:text-purple-700 dark:group-hover:text-purple-200'
                      }`}>{event.ten_su_kien}</h4>
                      <ExternalLink className="w-3 h-3 text-zinc-400 dark:text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <p className="text-[10px] text-zinc-400 dark:text-zinc-500 italic font-medium">{event.time_event || 'Không rõ thời gian'}</p>
                  </div>
                  
                  <div className="flex items-center gap-6 sm:gap-10 border-t md:border-t-0 md:border-l border-zinc-200 dark:border-zinc-800 pt-4 md:pt-0 md:pl-10">
                    <div className="text-center min-w-[60px]">
                      <p className="text-[9px] text-zinc-400 dark:text-zinc-500 uppercase font-mono mb-1 font-bold">Tổng điểm</p>
                      <p className="text-xl font-black text-zinc-900 dark:text-white font-mono">{event.total?.toLocaleString() ?? "0"}</p>
                    </div>
                    <div className="flex-1 min-w-[140px]">
                       <p className="text-[9px] text-zinc-400 dark:text-zinc-500 uppercase font-mono mb-2 text-center font-bold">Minh chứng (Sạch / Rác)</p>
                       <div className="h-2 w-full bg-zinc-200 dark:bg-zinc-800 rounded-full flex overflow-hidden">
                          <div className="bg-emerald-500 h-full transition-all duration-1000" style={{ width: `${event.total ? (event.clean / event.total) * 100 : 0}%` }} />
                          <div className="bg-red-500 h-full transition-all duration-1000" style={{ width: `${event.total ? (event.trash / event.total) * 100 : 0}%` }} />
                       </div>
                       <div className="flex justify-between mt-1 px-1">
                          <span className="text-[8px] text-emerald-600 dark:text-emerald-500 font-bold">{event.clean?.toLocaleString() ?? "0"} ({event.total ? Math.round((event.clean / event.total) * 100) : 0}%)</span>
                          <span className="text-[8px] text-red-600 dark:text-red-500 font-bold">{event.trash?.toLocaleString() ?? "0"} ({event.total ? Math.round((event.trash / event.total) * 100) : 0}%)</span>
                       </div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-12 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl bg-zinc-50 dark:bg-zinc-900/20">
                 <Ticket className="w-8 h-8 text-zinc-300 dark:text-zinc-700 mx-auto mb-4" />
                 <p className="text-zinc-400 dark:text-zinc-500 text-sm italic">Hệ thống chưa ghi nhận sự kiện {activeCategory === 'education' ? 'giáo dục' : 'showbiz'} nổi bật trong kỳ này.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    )}

      {/* Detail Comments (Only show if event is selected) */}
      {selectedEventId && eventDetail && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-top-4 duration-700">
          <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl">
            <div className="flex items-center gap-3 mb-6">
              <MessageCircle className="w-5 h-5 text-blue-500" />
              <h3 className="text-lg font-bold text-zinc-900 dark:text-white">Bình luận Tiêu biểu</h3>
            </div>
            <div className="space-y-4">
              {(() => {
                let comments: any[] = eventDetail.top_comments?.most_popular || 
                                      eventDetail.top_comments?.overall || 
                                      (Array.isArray(eventDetail.top_comments) ? eventDetail.top_comments : []) || [];
                
                // Prioritize adding variety from analysis examples
                if (eventDetail.analysis) {
                  Object.entries(eventDetail.analysis).forEach(([sentiment, data]: [string, any]) => {
                    if (data && data.examples && Array.isArray(data.examples)) {
                      data.examples.forEach((text: string) => {
                        // Check if this comment is already in the list
                        if (!comments.some(c => (c.text || c.content) === text)) {
                          comments.push({
                            text: text,
                            stance: sentiment,
                            emotion: sentiment,
                            score: data.percent
                          });
                        }
                      });
                    }
                  });
                }
                
                if (comments.length === 0) {
                  return <p className="text-zinc-500 dark:text-zinc-600 text-xs italic text-center py-10 font-mono">Không có bình luận nổi bật cho sự kiện này.</p>;
                }

                // Balance the comments by stance to ensure "Ý kiến riêng" shows up
                const sortedByVariety = [...comments].sort((a, b) => {
                  const sA = (a.stance || a.emotion || "").toLowerCase();
                  const sB = (b.stance || b.emotion || "").toLowerCase();
                  if (sA.includes('ý kiến') && !sB.includes('ý kiến')) return -1;
                  if (!sA.includes('ý kiến') && sB.includes('ý kiến')) return 1;
                  return 0;
                });

                const commentsToShow = sortedByVariety.slice(0, 15);
                
                return commentsToShow.map((comment: any, idx: number) => (
                  <div key={idx} className="p-5 bg-zinc-50 dark:bg-zinc-950/50 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm hover:border-blue-500/20 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[10px] font-mono text-zinc-400 dark:text-zinc-600 font-bold">#{comment.comment_id || `cmt_${idx}`}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                        (() => {
                           const s = (comment.emotion || comment.stance || "").toLowerCase().replace(/_/g, ' ');
                           if (s.includes('tiêu cực')) return 'bg-red-500/10 text-red-600 dark:text-red-400';
                           if (s.includes('tích cực')) return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400';
                           if (s.includes('ý kiến riêng')) return 'bg-amber-500/10 text-amber-600 dark:text-amber-400';
                           return 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400';
                        })()
                      }`}>
                        {comment.emotion || comment.stance || 'Phân tích'}
                      </span>
                    </div>
                    <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed italic">
                      "{comment.text || comment.content || comment.comment || comment.comment_text || JSON.stringify(comment)}"
                    </p>
                    <div className="mt-4 flex items-center gap-4 text-zinc-400 dark:text-zinc-500 font-mono text-[10px] font-bold">
                      {comment.score !== undefined && <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {typeof comment.score === 'string' ? `Percent: ${comment.score}` : `Score: ${comment.score}`}</span>}
                      {comment.likes !== undefined && <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> Likes: {comment.likes}</span>}
                    </div>
                  </div>
                ));
              })()}
            </div>
          </div>
          
          <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl dark:shadow-2xl flex flex-col justify-center items-center text-center">
             <div className="w-20 h-20 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center mb-6 border border-zinc-200 dark:border-zinc-700">
                <ChevronLeft className="w-10 h-10 text-zinc-400 dark:text-zinc-500" />
             </div>
             <h4 className="text-zinc-900 dark:text-white font-bold mb-2">Xem sự kiện khác?</h4>
             <p className="text-zinc-500 text-xs max-w-[250px] mb-8 font-medium">Bạn có thể quay lại danh sách tổng hợp để khám phá thêm các xu hướng dư luận khác.</p>
             <button 
                onClick={() => setSelectedEventId(null)}
                className="px-8 py-3 bg-blue-600 dark:bg-white text-white dark:text-black font-bold rounded-2xl hover:bg-blue-700 dark:hover:bg-zinc-200 transition-all shadow-lg"
             >
                Quay lại danh sách
             </button>
          </div>
        </div>
      )}

      {/* Alert List Placeholder (Only show if no event is selected) */}
      {!selectedEventId && (
        <div className="p-6 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 rounded-3xl shadow-sm">
          <div className="flex items-center gap-3 mb-4">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <h4 className="text-red-600 dark:text-red-400 font-black text-sm tracking-wide uppercase">Cảnh báo Toxic / Công kích cá nhân</h4>
          </div>
          <div className="space-y-2">
              <div className="text-zinc-700 dark:text-zinc-500 text-xs flex justify-between border-b border-zinc-200 dark:border-zinc-800 pb-2 font-medium">
                  <span>"Chửi bới, công kích người thân..."</span>
                  <span className="font-mono text-red-700 dark:text-red-900 font-bold">Detected in 12% comments</span>
              </div>
              <p className="text-zinc-400 dark:text-zinc-500 text-xs italic font-medium">Hệ thống đang tiếp tục trích xuất các bình luận vi phạm...</p>
          </div>
        </div>
      )}
    </div>
  );
}
