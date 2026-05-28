import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  AreaChart,
  Area
} from 'recharts';
import { motion, useMotionValue, useTransform, animate } from 'motion/react';
import { ArrowUpRight, GraduationCap, Ticket, Globe, Facebook, CheckCircle2, Clock } from 'lucide-react';
import { InsightsData } from '../../types';

/* ---- Animation primitives ---- */

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 90, damping: 16 }
  }
};

function AnimatedCounter({ value, className }: { value: number; className?: string }) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (latest) => Math.round(latest).toLocaleString());

  React.useEffect(() => {
    const controls = animate(count, value, {
      duration: 1.6,
      ease: [0.16, 1, 0.3, 1],
    });
    return controls.stop;
  }, [value]);

  return <motion.span className={className}>{rounded}</motion.span>;
}

export default function OverviewView({ data, theme = 'dark' }: { data: InsightsData, theme?: 'dark' | 'light' }) {
  const overall = data?.overall;

  const totalRaw = overall?.total_comments?.raw ?? 0;
  const totalClean = overall?.total_comments?.clean ?? 0;
  const totalTrash = overall?.total_comments?.trash ?? 0;
  const cleanPct = totalRaw ? Math.round((totalClean / totalRaw) * 100) : 0;
  const trashPct = totalRaw ? Math.round((totalTrash / totalRaw) * 100) : 0;

  const eduEvents = overall?.by_category?.education?.events ?? 0;
  const showbizEvents = overall?.by_category?.showbiz?.events ?? 0;
  const totalEvents = overall?.total_events ?? Math.max(1, eduEvents + showbizEvents);
  const eduPct = Math.round((eduEvents / totalEvents) * 100);
  const showbizPct = Math.round((showbizEvents / totalEvents) * 100);

  const eduComments = overall?.by_category?.education?.comments_clean ?? 0;
  const showbizComments = overall?.by_category?.showbiz?.comments_clean ?? 0;

  const websiteLinks = overall?.total_links_website ?? 0;
  const facebookLinks = overall?.total_links_facebook ?? 0;

  const analyzedEvents = overall?.total_events_with_analysis ?? 0;
  const pendingEvents = overall?.total_events_without_analysis ?? 0;
  const analyzedPct = totalEvents ? Math.round((analyzedEvents / totalEvents) * 100) : 0;

  // Sparkline placeholder data — visual rhythm without misleading users
  const sparkData = Array.from({ length: 24 }, (_, i) => ({
    x: i,
    y: 40 + Math.sin(i / 2.5) * 18 + (i % 5) * 3
  }));

  const gridStroke = theme === 'dark' ? '#27272a' : '#e4e4e7';
  const tooltipBg = theme === 'dark' ? '#0a0a0a' : '#ffffff';
  const tooltipBorder = theme === 'dark' ? '#27272a' : '#e4e4e7';

  return (
    <motion.div
      className="space-y-4"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {/* HERO ROW — large statement card + dual category split */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Hero number — span 7 */}
        <div className="lg:col-span-7 relative overflow-hidden rounded-3xl border border-zinc-200 dark:border-zinc-800/80 bg-gradient-to-br from-white via-white to-blue-50/40 dark:from-zinc-900 dark:via-zinc-900 dark:to-blue-950/30 p-8">
          <motion.div
            className="absolute -right-20 -top-20 w-64 h-64 bg-blue-500/10 dark:bg-blue-500/15 rounded-full blur-3xl pointer-events-none"
            animate={{ x: [0, 20, 0], y: [0, -10, 0], scale: [1, 1.1, 1] }}
            transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          />
          <motion.div
            className="absolute -left-10 -bottom-20 w-56 h-56 bg-indigo-500/8 dark:bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"
            animate={{ x: [0, -15, 0], y: [0, 10, 0], scale: [1.1, 1, 1.1] }}
            transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
          />

          <div className="relative">
            <div className="flex items-center gap-2 mb-6">
              <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400">
                <span className="relative flex w-1.5 h-1.5">
                  <span className="absolute inline-flex w-full h-full rounded-full bg-emerald-400 opacity-75 animate-ping" />
                  <span className="relative inline-flex rounded-full w-1.5 h-1.5 bg-emerald-500" />
                </span>
                Live · realtime intelligence
              </span>
            </div>

            <div className="flex items-baseline gap-3 flex-wrap">
              <AnimatedCounter
                value={totalRaw}
                className="text-6xl md:text-7xl font-bold text-zinc-900 dark:text-white tracking-tight tabular-nums leading-none"
              />
              <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">comments analyzed</span>
            </div>

            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400 max-w-md leading-relaxed">
              Sentiment intelligence across <span className="text-zinc-700 dark:text-zinc-200 font-medium">{totalEvents.toLocaleString()}</span> events from Vietnamese social discourse.
            </p>

            <motion.div
              className="mt-8 h-16 -mx-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6, duration: 1.2 }}
            >
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sparkData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                  <defs>
                    <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="y"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fill="url(#sparkFill)"
                    isAnimationActive={true}
                    animationDuration={1500}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </motion.div>

            <div className="mt-4 flex items-center gap-6 pt-4 border-t border-zinc-100 dark:border-zinc-800/80">
              <MiniMetric label="Clean" value={totalClean.toLocaleString()} pct={cleanPct} accent="emerald" />
              <div className="w-px h-8 bg-zinc-200 dark:bg-zinc-800" />
              <MiniMetric label="Filtered" value={totalTrash.toLocaleString()} pct={trashPct} accent="rose" />
              <div className="w-px h-8 bg-zinc-200 dark:bg-zinc-800 hidden sm:block" />
              <MiniMetric label="Events" value={totalEvents.toLocaleString()} pct={analyzedPct} accent="blue" hidden="sm" />
            </div>
          </div>
        </div>

        {/* Right column — Category split + Pipeline status */}
        <div className="lg:col-span-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
          {/* Education vs Showbiz split */}
          <motion.div
            variants={itemVariants}
            className="rounded-3xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 p-6 flex flex-col"
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Coverage by domain</h3>
              <ArrowUpRight className="w-4 h-4 text-zinc-300 dark:text-zinc-600" />
            </div>

            <div className="space-y-4 flex-1">
              <CategoryRow
                icon={<GraduationCap className="w-4 h-4" />}
                label="Education"
                events={eduEvents}
                comments={eduComments}
                pct={eduPct}
                color="bg-blue-500"
                trackColor="bg-blue-500/10"
              />
              <CategoryRow
                icon={<Ticket className="w-4 h-4" />}
                label="Showbiz"
                events={showbizEvents}
                comments={showbizComments}
                pct={showbizPct}
                color="bg-purple-500"
                trackColor="bg-purple-500/10"
              />
            </div>
          </motion.div>

          {/* Pipeline status mini */}
          <motion.div
            variants={itemVariants}
            className="rounded-3xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 p-6"
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Pipeline status</h3>
              <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">{analyzedPct}% done</span>
            </div>

            <div className="space-y-3">
              <PipelineRow
                icon={<CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                label="Analyzed"
                value={analyzedEvents}
                total={totalEvents}
                color="bg-emerald-500"
              />
              <PipelineRow
                icon={<Clock className="w-4 h-4 text-amber-500" />}
                label="Pending"
                value={pendingEvents}
                total={totalEvents}
                color="bg-amber-500"
              />
            </div>
          </motion.div>
        </div>
      </motion.div>

      {/* SECONDARY ROW — Source breakdown bar chart + Quality stats */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Source distribution */}
        <div className="lg:col-span-8 rounded-3xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-base font-semibold text-zinc-900 dark:text-white">Source distribution</h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Crawled links by platform</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <Legend dot="bg-amber-500" label="Website" value={websiteLinks} />
              <Legend dot="bg-violet-500" label="Facebook" value={facebookLinks} />
            </div>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  { name: 'Website', value: websiteLinks, color: '#f59e0b' },
                  { name: 'Facebook', value: facebookLinks, color: '#8b5cf6' },
                ]}
                layout="vertical"
                margin={{ left: 0, right: 24, top: 8, bottom: 8 }}
                barCategoryGap={24}
              >
                <XAxis type="number" hide />
                <YAxis
                  dataKey="name"
                  type="category"
                  stroke={theme === 'dark' ? '#a1a1aa' : '#52525b'}
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  width={86}
                />
                <Tooltip
                  cursor={{ fill: theme === 'dark' ? '#18181b' : '#fafafa' }}
                  contentStyle={{
                    backgroundColor: tooltipBg,
                    border: `1px solid ${tooltipBorder}`,
                    borderRadius: '12px',
                    boxShadow: '0 10px 30px -10px rgba(0,0,0,0.2)'
                  }}
                  itemStyle={{ color: theme === 'dark' ? '#fafafa' : '#18181b', fontSize: '12px' }}
                  labelStyle={{ color: theme === 'dark' ? '#fafafa' : '#18181b', fontWeight: 600 }}
                />
                <Bar dataKey="value" radius={[0, 8, 8, 0]} barSize={28}>
                  <Cell fill="#f59e0b" />
                  <Cell fill="#8b5cf6" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quality strip — vertical compact */}
        <div className="lg:col-span-4 rounded-3xl border border-zinc-200 dark:border-zinc-800/80 bg-zinc-50/50 dark:bg-zinc-900/50 p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-4">Data quality</h3>
            <div className="flex items-baseline gap-2 mb-1">
              <AnimatedCounter
                value={cleanPct}
                className="text-4xl font-bold text-zinc-900 dark:text-white tabular-nums"
              />
              <span className="text-2xl text-zinc-400">%</span>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">Of {totalRaw.toLocaleString()} raw records pass quality filters.</p>
          </div>

          <div className="mt-6 space-y-3">
            <QualityBar label="Clean" value={totalClean} total={totalRaw} color="emerald" />
            <QualityBar label="Filtered" value={totalTrash} total={totalRaw} color="rose" />
          </div>
        </div>
      </motion.div>

      {/* TERTIARY — feature cards (links to deeper views) */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FeatureCard
          icon={<GraduationCap className="w-5 h-5" />}
          title="Education domain"
          subtitle="Stance-based sentiment in academic discourse"
          metric={eduEvents.toLocaleString()}
          metricLabel="events"
          accent="blue"
        />
        <FeatureCard
          icon={<Ticket className="w-5 h-5" />}
          title="Showbiz domain"
          subtitle="Emotion analytics across entertainment events"
          metric={showbizEvents.toLocaleString()}
          metricLabel="events"
          accent="purple"
        />
      </motion.div>
    </motion.div>
  );
}

/* ---------- Sub-components ---------- */

function MiniMetric({
  label,
  value,
  pct,
  accent,
  hidden
}: {
  label: string;
  value: string;
  pct: number;
  accent: 'emerald' | 'rose' | 'blue';
  hidden?: 'sm';
}) {
  const dotMap: Record<string, string> = {
    emerald: 'bg-emerald-500',
    rose: 'bg-rose-500',
    blue: 'bg-blue-500',
  };
  return (
    <div className={hidden === 'sm' ? 'hidden sm:block' : ''}>
      <div className="flex items-center gap-1.5 mb-1">
        <span className={`w-1.5 h-1.5 rounded-full ${dotMap[accent]}`} />
        <span className="text-[10px] uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-medium">{label}</span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-base font-semibold text-zinc-900 dark:text-white tabular-nums">{value}</span>
        <span className="text-[11px] text-zinc-400 dark:text-zinc-500 tabular-nums">{pct}%</span>
      </div>
    </div>
  );
}

function CategoryRow({
  icon,
  label,
  events,
  comments,
  pct,
  color,
  trackColor
}: {
  icon: React.ReactNode;
  label: string;
  events: number;
  comments: number;
  pct: number;
  color: string;
  trackColor: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-zinc-700 dark:text-zinc-300">{icon}</span>
          <span className="text-sm font-medium text-zinc-900 dark:text-white">{label}</span>
        </div>
        <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 tabular-nums">{pct}%</span>
      </div>
      <div className={`h-1.5 w-full ${trackColor} rounded-full overflow-hidden`}>
        <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[11px] text-zinc-500 dark:text-zinc-400 tabular-nums">{events.toLocaleString()} events</span>
        <span className="text-[11px] text-zinc-500 dark:text-zinc-400 tabular-nums">{comments.toLocaleString()} cmts</span>
      </div>
    </div>
  );
}

function PipelineRow({
  icon,
  label,
  value,
  total,
  color
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const pct = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      {icon}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
          <span className="text-xs font-medium text-zinc-900 dark:text-white tabular-nums">{value.toLocaleString()}</span>
        </div>
        <div className="h-1 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
          <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

function Legend({ dot, label, value }: { dot: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className="font-semibold text-zinc-700 dark:text-zinc-200 tabular-nums">{value}</span>
    </div>
  );
}

function QualityBar({
  label,
  value,
  total,
  color
}: {
  label: string;
  value: number;
  total: number;
  color: 'emerald' | 'rose';
}) {
  const pct = total ? Math.round((value / total) * 100) : 0;
  const colorMap: Record<string, string> = {
    emerald: 'bg-emerald-500',
    rose: 'bg-rose-500',
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-medium">{label}</span>
        <span className="text-xs text-zinc-700 dark:text-zinc-200 tabular-nums">{value.toLocaleString()} <span className="text-zinc-400 dark:text-zinc-500">· {pct}%</span></span>
      </div>
      <div className="h-1.5 w-full bg-white dark:bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full ${colorMap[color]} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  subtitle,
  metric,
  metricLabel,
  accent
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  metric: string;
  metricLabel: string;
  accent: 'blue' | 'purple';
}) {
  const accentMap: Record<string, string> = {
    blue: 'hover:border-blue-500/50 from-blue-500/5 to-transparent',
    purple: 'hover:border-purple-500/50 from-purple-500/5 to-transparent',
  };
  const iconBgMap: Record<string, string> = {
    blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  };
  return (
    <motion.div
      whileHover={{ y: -4, transition: { type: 'spring', stiffness: 300, damping: 20 } }}
      whileTap={{ scale: 0.98 }}
      className={`group relative overflow-hidden rounded-3xl border border-zinc-200 dark:border-zinc-800/80 bg-gradient-to-br ${accentMap[accent]} bg-white dark:bg-zinc-900 p-6 transition-shadow hover:shadow-xl cursor-pointer`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl ${iconBgMap[accent]} flex items-center justify-center`}>
            {icon}
          </div>
          <div>
            <h4 className="text-sm font-semibold text-zinc-900 dark:text-white">{title}</h4>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 max-w-[260px]">{subtitle}</p>
          </div>
        </div>
        <motion.div
          className="text-zinc-300 dark:text-zinc-600 group-hover:text-zinc-700 dark:group-hover:text-zinc-300"
          whileHover={{ x: 2, y: -2 }}
        >
          <ArrowUpRight className="w-4 h-4" />
        </motion.div>
      </div>
      <div className="mt-6 flex items-baseline gap-2">
        <span className="text-3xl font-bold text-zinc-900 dark:text-white tabular-nums">{metric}</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">{metricLabel}</span>
      </div>
    </motion.div>
  );
}
