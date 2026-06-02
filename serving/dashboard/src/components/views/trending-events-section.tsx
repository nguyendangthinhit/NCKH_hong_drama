import React, { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts';
import { TrendingUp, Info } from 'lucide-react';

type RawEvent = {
  id_content: string;
  ten_su_kien: string;
  time_event?: string;
  total: number;
  clean: number;
  trash: number;
};

type MetricKey = 'trending' | 'volume' | 'engagement' | 'quality';

type ScoredEvent = RawEvent & {
  rate: number;
  decay: number;
  trending: number;
  volume: number;
  engagement: number;
  quality: number;
};

type MetricMeta = {
  key: MetricKey;
  label: string;
  short: string;
  formula: string;
  hint: string;
  format: (n: number) => string;
};

const TODAY = new Date();
const HALF_LIFE_DAYS = 180;
const MISSING_DATE_DECAY = 0.5;

const recencyDecay = (timeEvent?: string): number => {
  if (!timeEvent) return MISSING_DATE_DECAY;
  const d = new Date(timeEvent);
  if (isNaN(d.getTime())) return MISSING_DATE_DECAY;
  const days = (TODAY.getTime() - d.getTime()) / 86_400_000;
  if (days < 0) return 1;
  return Math.exp(-days / HALF_LIFE_DAYS);
};

const score = (e: RawEvent): ScoredEvent => {
  const total = e.total || 0;
  const clean = e.clean || 0;
  const rate = total > 0 ? clean / total : 0;
  const decay = recencyDecay(e.time_event);
  return {
    ...e,
    rate,
    decay,
    volume: total,
    engagement: clean,
    quality: rate,
    trending: clean * rate * decay,
  };
};

const fmtInt = (n: number) => Math.round(n).toLocaleString();
const fmtPct = (n: number) => `${(n * 100).toFixed(0)}%`;

const METRICS: MetricMeta[] = [
  {
    key: 'trending',
    label: 'Trending',
    short: 'Score',
    formula: 'clean × clean_rate × recency',
    hint: 'Tổng hợp: nhiều bình luận sạch, tỉ lệ sạch cao, sự kiện gần đây.',
    format: fmtInt,
  },
  {
    key: 'volume',
    label: 'Volume',
    short: 'Total',
    formula: 'total comments',
    hint: 'Tổng bình luận (gồm cả comment rác). Bản ranking gốc.',
    format: fmtInt,
  },
  {
    key: 'engagement',
    label: 'Engagement',
    short: 'Clean',
    formula: 'clean comments',
    hint: 'Chỉ đếm bình luận đã lọc rác — phản ánh thảo luận thực.',
    format: fmtInt,
  },
  {
    key: 'quality',
    label: 'Quality',
    short: 'Rate',
    formula: 'clean / total',
    hint: 'Tỉ lệ comment sạch — sự kiện ít drama nội bộ comment.',
    format: fmtPct,
  },
];

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

interface Props {
  events: RawEvent[];
  onSelect: (id: string) => void;
}

const Pill: React.FC<{ active: boolean; onClick: () => void; label: string }> = ({ active, onClick, label }) => (
  <button
    onClick={onClick}
    className={`px-3 py-1.5 text-xs font-bold rounded-full transition-all ${
      active
        ? 'bg-purple-600 text-white shadow-md'
        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
    }`}
  >
    {label}
  </button>
);

const MetricCell: React.FC<{ meta: MetricMeta; value: number; active: boolean }> = ({ meta, value, active }) => (
  <div className={`text-center min-w-[58px] transition-opacity ${active ? 'opacity-100' : 'opacity-40'}`}>
    <p className={`text-[9px] uppercase font-bold mb-1 ${active ? 'text-purple-600 dark:text-purple-400' : 'text-zinc-400'}`}>
      {meta.short}
    </p>
    <p className={`font-black ${active ? 'text-lg text-zinc-900 dark:text-white' : 'text-xs text-zinc-500'}`}>
      {meta.format(value)}
    </p>
  </div>
);

export const TrendingEventsSection: React.FC<Props> = ({ events, onSelect }) => {
  const [metric, setMetric] = useState<MetricKey>('trending');
  const meta = METRICS.find((m) => m.key === metric)!;

  const ranked = useMemo(() => {
    const scored = (events ?? []).map(score);
    return scored
      .sort((a, b) => (b[metric] as number) - (a[metric] as number))
      .slice(0, 5)
      .map((e, i) => ({
        ...e,
        fillColor: COLORS[i % COLORS.length],
        displayName: e.ten_su_kien?.length > 25 ? e.ten_su_kien.substring(0, 25) + '...' : e.ten_su_kien,
      }));
  }, [events, metric]);

  return (
    <div className="p-8 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-xl overflow-hidden relative">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-purple-600" />
          <h3 className="text-xl font-bold text-zinc-900 dark:text-white">Sự kiện Trending</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          {METRICS.map((m) => (
            <Pill key={m.key} label={m.label} active={metric === m.key} onClick={() => setMetric(m.key)} />
          ))}
        </div>
      </div>

      <div className="flex items-start gap-2 mb-8 px-3 py-2 bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-purple-900/40 rounded-xl">
        <Info className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400 mt-0.5 flex-shrink-0" />
        <div className="text-[11px] leading-relaxed">
          <span className="font-mono font-bold text-purple-700 dark:text-purple-300">{meta.formula}</span>
          <span className="text-zinc-600 dark:text-zinc-400 ml-2">— {meta.hint}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-12">
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={ranked}
              layout="vertical"
              onClick={(d: any) => d?.activePayload && onSelect(d.activePayload[0].payload.id_content)}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" hide />
              <YAxis dataKey="displayName" type="category" fontSize={10} width={120} />
              <Tooltip
                formatter={(value: number) => [meta.format(value), meta.label]}
                labelFormatter={(l: string) => l}
              />
              <Bar dataKey={metric} radius={[0, 4, 4, 0]} className="cursor-pointer">
                {ranked.map((entry, index) => (
                  <Cell key={`bar-${index}`} fill={entry.fillColor} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="h-80 w-full bg-zinc-900/10 dark:bg-zinc-100/5 p-4 rounded-2xl relative z-10">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="clean"
                name="Clean"
                domain={['auto', 'auto']}
                padding={{ left: 40, right: 40 }}
              />
              <YAxis
                type="number"
                dataKey="trash"
                name="Trash"
                domain={['auto', 'auto']}
                padding={{ top: 40, bottom: 40 }}
              />
              <ZAxis type="number" dataKey={metric} range={[400, 3000]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={ranked} onClick={(d: any) => onSelect(d.id_content)}>
                {ranked.map((entry, index) => (
                  <Cell key={`bubble-${index}`} fill={entry.fillColor} fillOpacity={0.7} className="cursor-pointer" />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      <h3 className="text-xl font-bold text-zinc-900 dark:text-white mb-6">Danh sách chi tiết</h3>
      <div className="grid grid-cols-1 gap-4">
        {ranked.map((event, index) => (
          <div
            key={event.id_content}
            onClick={() => onSelect(event.id_content)}
            className="p-5 bg-zinc-50 dark:bg-zinc-950/50 border border-zinc-200 dark:border-zinc-800 rounded-2xl flex flex-col md:flex-row justify-between gap-4 cursor-pointer hover:border-purple-500 shadow-sm transition-all group"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <span className="bg-zinc-200 dark:bg-zinc-800 text-xs font-bold px-2 py-0.5 rounded">
                  #{index + 1}
                </span>
                <span className="text-[10px] font-mono text-zinc-400">ID: {event.id_content}</span>
              </div>
              <h4 className="text-sm font-bold text-zinc-900 dark:text-white group-hover:text-purple-600 transition-colors">
                {event.ten_su_kien}
              </h4>
              <p className="text-[10px] text-zinc-400 italic">{event.time_event || 'Unknown date'}</p>
            </div>

            <div className="flex items-center gap-4 md:gap-6 border-t md:border-t-0 md:border-l border-zinc-200 dark:border-zinc-800 pt-4 md:pt-0 md:pl-6">
              {METRICS.map((m) => (
                <MetricCell
                  key={m.key}
                  meta={m}
                  value={event[m.key] as number}
                  active={m.key === metric}
                />
              ))}

              <div className="flex-1 min-w-[100px] hidden lg:block">
                <p className="text-[9px] text-zinc-400 uppercase font-bold mb-1">Mix</p>
                <div className="h-2 w-full bg-zinc-200 dark:bg-zinc-800 rounded-full flex overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full"
                    style={{ width: `${event.total ? (event.clean / event.total) * 100 : 0}%` }}
                  />
                  <div
                    className="bg-red-500 h-full"
                    style={{ width: `${event.total ? (event.trash / event.total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
