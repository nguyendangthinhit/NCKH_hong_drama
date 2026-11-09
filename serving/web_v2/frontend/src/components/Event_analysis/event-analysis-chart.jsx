import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import styles from './event-analysis.module.scss';

export default function EventAnalysisChart({ groups, validCount }) {
  if (validCount === 0) return <p className={styles.notice}>Chưa có bình luận hợp lệ để vẽ biểu đồ.</p>;

  return (
    <div className={styles.chart} role="img" aria-label="Biểu đồ phân bố bình luận; số liệu chi tiết trong bảng bên dưới.">
      <ResponsiveContainer width="100%" height={260} minWidth={0}>
        <PieChart>
          <Pie
            data={groups.filter((group) => group.count > 0)}
            dataKey="count"
            nameKey="label"
            cx="50%"
            cy="50%"
            innerRadius={62}
            outerRadius={95}
            isAnimationActive={false}
          >
            {groups.filter((group) => group.count > 0).map((group) => (
              <Cell key={group.key} fill={group.color} stroke="#fff" />
            ))}
          </Pie>
          <Tooltip formatter={(value, name) => [`${Number(value).toLocaleString('vi-VN')} bình luận`, name]} />
          <text x="50%" y="48%" textAnchor="middle" fill="currentColor" fontSize={20} fontWeight={700}>
            {validCount.toLocaleString('vi-VN')}
          </text>
          <text x="50%" y="58%" textAnchor="middle" fill="currentColor" fontSize={12}>bình luận hợp lệ</text>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
