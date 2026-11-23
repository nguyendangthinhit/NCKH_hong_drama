import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Màu cố định theo nhãn để 2 lĩnh vực đọc nhất quán (tiêu cực = đỏ/cam, tích cực = xanh, trung lập = xám).
export const LABEL_COLORS = {
  'Phẫn nộ': '#d9480f', 'Cà khịa': '#e8a33d', 'Đồng cảm': '#4c8bf5', 'Ủng hộ': '#2f9e6b', 'Trung lập': '#8a94a6',
  'tiêu cực': '#d9480f', 'tích cực': '#2f9e6b', 'trung lập': '#8a94a6', 'ý kiến riêng': '#7b61d1',
  'chửi bới': '#c92a2a', 'công kích cá nhân': '#e8590c', 'công kích người thân': '#a61e4d',
}

// Biểu đồ cột ngang: số comment theo từng nhãn, kèm phần trăm.
export default function LabelChart({ data, nameKey = 'label' }) {
  const total = data.reduce((s, d) => s + d.count, 0)
  const rows = data.map((d) => ({ ...d, name: d[nameKey], pct: total ? `${Math.round((d.count / total) * 100)}%` : '0%' }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 44)}>
      <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 48 }}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={130} tick={{ fill: 'var(--text)', fontSize: 13 }} axisLine={false} tickLine={false} />
        <Tooltip formatter={(v) => [`${v} comment`, 'Số lượng']} cursor={{ fill: 'var(--hover)' }}
          contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={22} isAnimationActive={false}>
          {rows.map((r) => <Cell key={r.name} fill={LABEL_COLORS[r.name] || '#4c8bf5'} />)}
          <LabelList dataKey="pct" position="right" style={{ fill: 'var(--muted)', fontSize: 12 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
