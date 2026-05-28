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
  CartesianGrid,
  ScatterChart,
  Scatter,
  ZAxis
} from 'recharts';
import { InsightsData, StanceDistribution } from '../../types';
import { GraduationCap, Ticket, Activity, ChevronLeft, ExternalLink, MessageCircle, TrendingUp, Users } from 'lucide-react';

const STANCE_COLORS: Record<string, string> = {
  'tích cực': '#10b981',
  'tiêu cực': '#ef4444',
  'trung lập': '#71717a',
  'ý kiến riêng': '#f59e0b',
  'ý kiến': '#f59e0b',
  'tích_cực': '#10b981',
  'tiêu_cực': '#ef4444',
  'trung_lập': '#71717a',
  'ý_kiến_riêng': '#f59e0b',
};

const EMOTION_COLORS: Record<string, string> = {
  'tích cực': '#10b981',
  'tiêu cực': '#ef4444',
  'trung lập': '#71717a',
  'ý kiến riêng': '#f59e0b',
  'phẫn nộ': '#ef4444',
  'cà khịa': '#f59e0b',
  'đồng cảm': '#3b82f6',
  'ủng hộ': '#10b981',
};

const GET_COLOR = (key: string, category: 'education' | 'showbiz') => {
  const k = key.toLowerCase().trim().replace(/_/g, ' ');
  const colors = category === 'education' ? STANCE_COLORS : EMOTION_COLORS;
  if (colors[k]) return colors[k];
  if (k.includes('tiêu cực')) return STANCE_COLORS['tiêu cực'];
  if (k.includes('tích cực')) return STANCE_COLORS['tích cực'];
  if (k.includes('trung lập')) return STANCE_COLORS['trung lập'];
  if (k.includes('ý kiến')) return STANCE_COLORS['ý kiến riêng'];
  return '#8884d8';
};

const BASE_RAW_URL = "https://raw.githubusercontent.com/nguyendangthinhit/NCKH_hong_drama/main/data";

interface EventDetailData {
  id_content: string;
  event_name: string;
  total_comments?: number;
  comment_counts?: Record<string, number>;
  emotion_stats?: Record<string, number>;
  stance_stats?: Record<string, number>;
  analysis?: any;
  top_comments?: any;
  controversial_threads?: any[];
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
  
  const [keywordsData, setKeywordsData] = useState<any>(null);
  
  const categoryData = data?.[activeCategory];

  useEffect(() => {
    fetchKeywordsData();
  }, []);

  const fetchKeywordsData = async () => {
    try {
      const response = await fetch(`${BASE_RAW_URL}/analysis-output/keyword_analysis_v4.json`);
      if (response.ok) {
        const json = await response.json();
        setKeywordsData(json);
      }
    } catch (err) {
      console.error("Error fetching keywords:", err);
    }
  };

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
      // Education uses analyzed_dataa (double-a), showbiz uses analyzed_data
      const folder = activeCategory === 'education' ? 'process_education/analyzed_dataa' : 'process_showbiz/analyzed_data';
      const url = `${BASE_RAW_URL}/processed/${folder}/summary/${id}.json`;
      console.log("Fetching event detail from:", url);
      const response = await fetch(url);

      if (!response.ok) throw new Error(`Could not load event data (${id}). Status: ${response.status}`);
      const json = await response.json();
      setEventDetail(json);
    } catch (err) {
      console.error("Error fetching event detail:", err);
      setError(err instanceof Error ? err.message : 'Error fetching data.');
    } finally {
      setIsLoading(false);
    }
  };

  const currentDistribution: StanceDistribution = activeCategory === 'education' 
    ? categoryData?.stance_distribution ?? {} 
    : categoryData?.emotion_distribution ?? {};
  
  const distributionToUse = eventDetail 
    ? (eventDetail.comment_counts || eventDetail.emotion_stats || eventDetail.stance_stats || {})
    : currentDistribution;

  const chartData = Object.entries(distributionToUse || {}).map(([key, value]) => {
    if (key === 'total') return null; // Skip total key if present in distribution
    const count = typeof value === 'object' ? (value as any).count : (value as number);
    const totalRaw = Object.entries(distributionToUse).reduce((acc: number, [k, v]) => {
      if (k === 'total') return acc;
      return acc + (typeof v === 'object' ? (v as any).count : (v as number));
    }, 0) || 1;
    
    return {
      name: key.replace(/_/g, ' ').toUpperCase(),
      value: count ?? 0,
      percent: `${Math.round((count / totalRaw) * 100)}%`,
      color: GET_COLOR(key, activeCategory)
    };
  }).filter(Boolean).sort((a: any, b: any) => b.value - a.value) as any[];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex p-1 bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl w-fit">
          <button 
            onClick={() => { setActiveCategory('education'); setSelectedEventId(null); }}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeCategory === 'education' ? 'bg-blue-600 text-white shadow-lg' : 'text-zinc-500'}`}
          >
            <GraduationCap className="w-4 h-4" /> Giáo dục
          </button>
          <button 
            onClick={() => { setActiveCategory('showbiz'); setSelectedEventId(null); }}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${activeCategory === 'showbiz' ? 'bg-purple-600 text-white shadow-lg' : 'text-zinc-500'}`}
          >
            <Ticket className="w-4 h-4" /> Showbiz
          </button>
        </div>
        {selectedEventId && (
          <button onClick={() => setSelectedEventId(null)} className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-zinc-800 rounded-xl text-sm font-medium border border-zinc-200 dark:border-zinc-700 shadow-sm">
            <ChevronLeft className="w-4 h-4" /> Quay lại
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-2xl text-red-600 dark:text-red-400 text-sm font-medium flex items-center gap-2">
          <Activity className="w-4 h-4" />
          <span>Không thể tải dữ liệu: {error}</span>
          <button onClick={() => selectedEventId && fetchEventDetail(selectedEventId)} className="ml-auto underline">Thử lại</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl relative">
          {isLoading && <div className="absolute inset-0 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm z-50 flex items-center justify-center rounded-3xl"><div className="w-8 h-8 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" /></div>}
          <h3 className="text-xl font-bold text-zinc-900 dark:text-white mb-8">{selectedEventId ? 'Chi tiết' : 'Dư luận'}</h3>
          <div className="h-80 w-full flex items-center justify-center">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={chartData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value" nameKey="name">
                    {chartData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />)}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : <p className="text-zinc-500 italic">No data available.</p>}
          </div>
        </div>
        <div className="space-y-4">
          {chartData.map((item: any) => (
            <div key={item.name}>
              <LegendItem 
                color={item.color} 
                name={item.name} 
                value={item.value} 
                percent={item.percent} 
              />
            </div>
          ))}
        </div>
      </div>

      {!selectedEventId && (
        <div className="space-y-6">
          {/* Keyword Analysis Section */}
          {keywordsData && keywordsData[activeCategory.toUpperCase()] && (
            <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl overflow-hidden">
               <div className="flex items-center gap-2 mb-8">
                <Activity className="w-5 h-5 text-blue-600" />
                <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Phân tích Từ khóa (Bag of Words)</h3>
              </div>
              <div className="h-[400px] w-full">
                {(() => {
                  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];
                  const sortedKeywords = [...keywordsData[activeCategory.toUpperCase()]]
                    .sort((a: any, b: any) => b.total_frequency - a.total_frequency)
                    .slice(0, 20)
                    .map((item, index) => ({
                      ...item,
                      color: colors[index % colors.length]
                    }));

                  return (
                    <>
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 20, right: 30, bottom: 40, left: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#27272a' : '#e4e4e7'} />
                          <XAxis 
                            type="number" 
                            dataKey="total_frequency" 
                            name="Frequency" 
                            stroke={theme === 'dark' ? '#52525b' : '#71717a'} 
                            fontSize={10}
                            label={{ value: 'Số lượng lặp (Total Frequency)', position: 'insideBottom', offset: -5, fontSize: 10, fill: theme === 'dark' ? '#52525b' : '#71717a' }}
                          />
                          <YAxis 
                            type="number" 
                            dataKey="total_articles" 
                            name="Articles" 
                            stroke={theme === 'dark' ? '#52525b' : '#71717a'} 
                            fontSize={10}
                            label={{ value: 'Số bài báo', angle: -90, position: 'insideLeft', fontSize: 10, fill: theme === 'dark' ? '#52525b' : '#71717a' }}
                          />
                          <ZAxis type="number" dataKey="pmi_score" range={[100, 1000]} name="PMI Score" />
                          <Tooltip 
                            cursor={{ strokeDasharray: '3 3' }}
                            content={({ active, payload }) => {
                              if (active && payload && payload.length) {
                                const item = payload[0].payload;
                                return (
                                  <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-3 rounded-xl shadow-xl">
                                    <p className="text-sm font-bold text-blue-600 mb-1" style={{ color: item.color }}>{item.keyword}</p>
                                    <div className="space-y-1">
                                      <p className="text-[10px] text-zinc-500 font-mono">Frequency: {item.total_frequency}</p>
                                      <p className="text-[10px] text-zinc-500 font-mono">PMI Score: {item.pmi_score}</p>
                                      <p className="text-[10px] text-zinc-500 font-mono">Articles: {item.total_articles}</p>
                                      <p className="text-[10px] text-zinc-500 font-mono">Type: {item.ngram_type}</p>
                                    </div>
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                          <Scatter name="Keywords" data={sortedKeywords}>
                            {sortedKeywords.map((entry, index) => (
                              <Cell 
                                key={`keyword-cell-${index}`} 
                                fill={entry.color} 
                                fillOpacity={0.6}
                                stroke={entry.color}
                              />
                            ))}
                          </Scatter>
                        </ScatterChart>
                      </ResponsiveContainer>
                      <div className="mt-8 pt-6 border-t border-zinc-100 dark:border-zinc-800 flex flex-wrap gap-2 justify-center">
                        {sortedKeywords.slice(0, 15).map((kw: any, i: number) => (
                          <div key={i} className="flex items-center gap-1.5 px-3 py-1 bg-zinc-50 dark:bg-zinc-800/50 rounded-full border border-zinc-100 dark:border-zinc-800 shadow-sm">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: kw.color }} />
                            <span className="text-[10px] font-bold text-zinc-600 dark:text-zinc-400">
                              {kw.keyword}
                            </span>
                          </div>
                        ))}
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          )}

          <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl overflow-hidden relative">
            <div className="flex items-center gap-2 mb-8">
              <TrendingUp className="w-5 h-5 text-purple-600" />
              <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Sự kiện Trending</h3>
            </div>
            
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-12">
              {(() => {
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
                const trendingEvents = (categoryData?.top_events_by_comments ?? [])
                  .sort((a: any, b: any) => (b.total || 0) - (a.total || 0))
                  .slice(0, 5)
                  .map((e: any, i: number) => ({
                    ...e,
                    fillColor: colors[i % colors.length],
                    displayName: (e.ten_su_kien?.length > 25) ? e.ten_su_kien.substring(0, 25) + "..." : e.ten_su_kien
                  }));

                return (
                  <>
                    <div className="h-80 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={trendingEvents} layout="vertical" onClick={(d: any) => d && d.activePayload && setSelectedEventId(d.activePayload[0].payload.id_content)}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                          <XAxis type="number" hide />
                          <YAxis dataKey="displayName" type="category" fontSize={10} width={120} />
                          <Tooltip />
                          <Bar dataKey="total" radius={[0, 4, 4, 0]} className="cursor-pointer">
                            {trendingEvents.map((entry, index) => <Cell key={`bar-${index}`} fill={entry.fillColor} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="h-80 w-full bg-zinc-900/10 dark:bg-zinc-100/5 p-4 rounded-2xl relative z-10">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" dataKey="clean" name="Clean" domain={['auto', 'auto']} padding={{ left: 40, right: 40 }} />
                          <YAxis type="number" dataKey="trash" name="Trash" domain={['auto', 'auto']} padding={{ top: 40, bottom: 40 }} />
                          <ZAxis type="number" dataKey="total" range={[400, 3000]} />
                          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                          <Scatter data={trendingEvents} onClick={(d) => setSelectedEventId(d.id_content)}>
                            {trendingEvents.map((entry, index) => <Cell key={`bubble-${index}`} fill={entry.fillColor} fillOpacity={0.7} className="cursor-pointer" />)}
                          </Scatter>
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  </>
                );
              })()}
            </div>

            <h3 className="text-xl font-bold text-zinc-900 dark:text-white mb-6">Danh sách chi tiết</h3>
            <div className="grid grid-cols-1 gap-4">
              {(categoryData?.top_events_by_comments ?? []).sort((a: any, b: any) => (b.total || 0) - (a.total || 0)).slice(0, 5).map((event: any, index: number) => (
                <div key={event.id_content} onClick={() => setSelectedEventId(event.id_content)} className="p-5 bg-zinc-50 dark:bg-zinc-950/50 border rounded-2xl flex flex-col md:flex-row justify-between gap-4 cursor-pointer hover:border-blue-500 shadow-sm transition-all group">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                       <span className="bg-zinc-200 dark:bg-zinc-800 text-xs font-bold px-2 py-0.5 rounded">#{index + 1}</span>
                       <span className="text-[10px] font-mono text-zinc-400">ID: {event.id_content}</span>
                    </div>
                    <h4 className="text-sm font-bold text-zinc-900 dark:text-white group-hover:text-blue-600 transition-colors">{event.ten_su_kien}</h4>
                    <p className="text-[10px] text-zinc-400 italic">{event.time_event || "Unknown date"}</p>
                  </div>
                  <div className="flex items-center gap-10 border-t md:border-t-0 md:border-l border-zinc-200 dark:border-zinc-800 pt-4 md:pt-0 md:pl-10">
                    <div className="text-center min-w-[60px]">
                      <p className="text-[9px] text-zinc-400 uppercase font-bold mb-1">Volume</p>
                      <p className="text-lg font-black text-zinc-900 dark:text-white">{event.total?.toLocaleString() ?? "0"}</p>
                    </div>
                    <div className="flex-1 min-w-[140px]">
                       <div className="h-2 w-full bg-zinc-200 dark:bg-zinc-800 rounded-full flex overflow-hidden">
                          <div className="bg-emerald-500 h-full" style={{ width: `${event.total ? (event.clean / event.total) * 100 : 0}%` }} />
                          <div className="bg-red-500 h-full" style={{ width: `${event.total ? (event.trash / event.total) * 100 : 0}%` }} />
                       </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {selectedEventId && eventDetail && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
          <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl">
            <div className="mb-8">
              <h3 className="text-2xl font-black text-zinc-900 dark:text-white mb-2 leading-tight">{eventDetail.event_name}</h3>
              <div className="flex items-center gap-4">
                <span className="text-xs font-mono text-zinc-400">ID: {eventDetail.id_content}</span>
                {eventDetail.total_comments !== undefined && (
                  <span className="text-xs font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">
                    {eventDetail.total_comments.toLocaleString()} bình luận
                  </span>
                )}
              </div>
            </div>

            {activeCategory === 'education' && eventDetail.analysis && (
              <div className="mb-10 space-y-6">
                <h4 className="text-sm font-bold uppercase tracking-widest text-zinc-400 mb-4">Phân tích sắc thái chi tiết</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(eventDetail.analysis).map(([sentiment, info]: [string, any]) => {
                    if (!info.summary) return null;
                    const color = GET_COLOR(sentiment, 'education');
                    return (
                      <div key={sentiment} className="p-5 border border-zinc-100 dark:border-zinc-800 rounded-2xl bg-zinc-50/30 dark:bg-zinc-900/30">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                          <span className="font-bold text-zinc-900 dark:text-white capitalize">{sentiment} ({info.percent})</span>
                        </div>
                        <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed italic">
                          {info.summary}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {activeCategory === 'showbiz' && eventDetail.emotion_stats && (
              <div className="mb-10 space-y-6">
                <h4 className="text-sm font-bold uppercase tracking-widest text-zinc-400 mb-4">Phân bổ cảm xúc chi tiết</h4>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(eventDetail.emotion_stats).map(([emotion, count]) => {
                    const total = Object.values(eventDetail.emotion_stats || {}).reduce((a, b) => a + (b as number), 0) || 1;
                    const percent = Math.round(((count as number) / total) * 100);
                    const color = GET_COLOR(emotion, 'showbiz');
                    
                    return (
                      <div key={emotion} className="flex-1 min-w-[120px] p-4 border border-zinc-100 dark:border-zinc-800 rounded-2xl bg-zinc-50/30 dark:bg-zinc-900/30">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                          <span className="text-[10px] font-bold uppercase text-zinc-500 dark:text-zinc-400">{emotion}</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                          <span className="text-xl font-black text-zinc-900 dark:text-white font-mono">{percent}%</span>
                          <span className="text-[10px] text-zinc-400">({count} cmt)</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between mb-8 pt-6 border-t border-zinc-100 dark:border-zinc-800">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/10 rounded-lg">
                  <MessageCircle className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Bình luận tiêu biểu</h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Những ý kiến phản hồi có tính lan tỏa và đại diện cao nhất</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {(() => {
                let comments: any[] = [];
                
                if (activeCategory === 'showbiz') {
                  // Showbiz structure: top_comments.most_popular
                  comments = eventDetail.top_comments?.most_popular || [];
                } else {
                  // Education structure: analysis[sentiment].examples
                  if (eventDetail.analysis) {
                    Object.entries(eventDetail.analysis).forEach(([sentiment, data]: [string, any]) => {
                      if (Array.isArray(data.examples)) {
                        data.examples.forEach((example: string) => {
                          comments.push({
                            text: example,
                            stance: sentiment,
                            label: sentiment
                          });
                        });
                      }
                    });
                  }
                  
                  // Fallback to top_comments if empty
                  if (comments.length === 0) {
                    comments = Array.isArray(eventDetail.top_comments) ? eventDetail.top_comments : [];
                  }
                }
                
                if (comments.length === 0) {
                  return (
                    <div className="p-12 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl bg-zinc-50/50 dark:bg-zinc-900/20">
                      <MessageCircle className="w-8 h-8 text-zinc-300 dark:text-zinc-700 mx-auto mb-4" />
                      <p className="text-zinc-400 dark:text-zinc-500 text-sm italic">Không có dữ liệu bình luận cho sự kiện này.</p>
                    </div>
                  );
                }

                return comments.slice(0, 15).map((comment: any, idx: number) => {
                  const text = typeof comment === 'string' ? comment : (comment.text || comment.content || comment.comment || "Nội dung bình luận không khả dụng");
                  const stance = comment.emotion || comment.stance || comment.label || "";
                  const bgColor = GET_COLOR(stance, activeCategory);
                  
                  return (
                    <div 
                      key={idx} 
                      className="group p-5 bg-zinc-50 dark:bg-zinc-950/40 border border-zinc-100 dark:border-zinc-800/50 rounded-2xl hover:border-blue-500/30 hover:bg-white dark:hover:bg-zinc-900/40 transition-all shadow-sm"
                    >
                      <div className="flex items-start gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-3">
                            <div className="w-1 h-3 rounded-full bg-blue-500/50" />
                            {stance && (
                              <span 
                                className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider text-white shadow-sm"
                                style={{ backgroundColor: bgColor }}
                              >
                                {stance.replace(/_/g, ' ')}
                              </span>
                            )}
                            {comment.likes !== undefined && (
                              <span className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500">
                                Likes: {comment.likes}
                              </span>
                            )}
                            {comment.score && !comment.likes && (
                              <span className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500">
                                Score: {comment.score}
                              </span>
                            )}
                          </div>
                          <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed text-sm italic font-medium">
                            "{text}"
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </div>

          {activeCategory === 'showbiz' && eventDetail.controversial_threads && eventDetail.controversial_threads.length > 0 && (
            <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl border-l-[6px] border-l-red-500">
              <div className="flex items-center gap-3 mb-8">
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <Users className="w-5 h-5 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Cuộc tranh luận sôi nổi</h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Các chủ đề gây tranh cãi và thu hút nhiều luồng ý kiến trái chiều</p>
                </div>
              </div>

              <div className="space-y-4">
                {eventDetail.controversial_threads.map((thread: any, idx: number) => (
                  <div key={idx} className="p-6 bg-zinc-50/50 dark:bg-zinc-950/30 border border-zinc-100 dark:border-zinc-800/50 rounded-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-3">
                      <Activity className="w-4 h-4 text-red-500/30 animate-pulse" />
                    </div>
                    
                    <div className="mb-4">
                      <p className="text-zinc-800 dark:text-zinc-200 font-medium leading-relaxed mb-4 italic">
                        "{thread.text}"
                      </p>
                      
                      {thread.thread_stats && (
                        <div className="flex flex-wrap items-center gap-4 border-t border-zinc-200/50 dark:border-zinc-800/50 pt-4">
                          <div className="px-3 py-1 bg-zinc-200/50 dark:bg-zinc-800/50 rounded-full text-[10px] font-bold text-zinc-600 dark:text-zinc-400 uppercase">
                            {thread.thread_stats.total} phản hồi
                          </div>
                          
                          <div className="flex items-center gap-2">
                            {Object.entries(thread.thread_stats.emotions || {}).map(([emotion, count]: [string, any]) => (
                                <span key={emotion} className="text-[10px] font-medium text-zinc-500 dark:text-zinc-400">
                                  {emotion}: {count}
                                </span>
                            ))}
                          </div>

                          {thread.thread_stats.toxic_count > 0 && (
                            <span className="ml-auto text-[10px] font-black text-red-500 uppercase tracking-widest">
                              Toxic Detected
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
