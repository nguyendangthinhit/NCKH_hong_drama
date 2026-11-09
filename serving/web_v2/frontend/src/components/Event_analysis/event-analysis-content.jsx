import EventAnalysisChart from './event-analysis-chart';
import styles from './event-analysis.module.scss';

const formatCount = (value) => value.toLocaleString('vi-VN');
const formatPercent = (value) => `${value.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}%`;

export default function EventAnalysisContent({ data }) {
  const summaries = data.groups.filter((group) => group.summary);
  const hasConclusion = data.conclusion.focus || data.conclusion.trend;

  return (
    <div className={styles.analysis}>
      <p className={styles.intro}>
        Phân bố {data.kind} trong tập bình luận đã thu thập và phân tích của sự kiện này.
        Kết quả không đại diện cho toàn bộ dư luận xã hội.
      </p>
      <dl className={styles.metrics}>
        <div><dt>Bình luận hợp lệ</dt><dd>{formatCount(data.validCount)}</dd></div>
        <div><dt>Đã phân loại {data.kind}</dt><dd>{formatCount(data.classifiedCount)}</dd></div>
        {data.trashCount !== null && <div><dt>Bình luận rác đã loại</dt><dd>{formatCount(data.trashCount)}</dd></div>}
        {data.unclassifiedCount > 0 && <div><dt>Chưa phân loại</dt><dd>{formatCount(data.unclassifiedCount)}</dd></div>}
      </dl>

      <EventAnalysisChart groups={data.groups} validCount={data.validCount} />
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <caption>Tỷ lệ tính trên {formatCount(data.validCount)} bình luận hợp lệ, không gồm bình luận rác.</caption>
          <thead><tr><th scope="col">Nhóm {data.kind}</th><th scope="col">Số lượng</th><th scope="col">Tỷ lệ</th></tr></thead>
          <tbody>
            {data.groups.map((group) => (
              <tr key={group.key}>
                <th scope="row"><span className={styles.dot} style={{ background: group.color }} />{group.label}</th>
                <td>{formatCount(group.count)}</td><td>{formatPercent(group.percent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.unclassifiedCount > 0 && (
        <p className={styles.note}>“Chưa phân loại” là bình luận hợp lệ chưa có nhãn trong summary, không phải bình luận rác.</p>
      )}

      {summaries.length > 0 && (
        <section className={styles.block} aria-label="Diễn giải các nhóm ý kiến">
          <h3>Diễn giải các nhóm ý kiến</h3>
          <div className={styles.summaries}>
            {summaries.map((group) => (
              <div className={styles.summary} key={group.key} style={{ borderLeftColor: group.color }}>
                <h4>{group.label} · {formatPercent(group.percent)}</h4>
                <p>{group.summary}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      {hasConclusion && (
        <section className={styles.block} aria-label="Nhận định từ dữ liệu phân tích">
          <h3>Nhận định từ dữ liệu phân tích</h3>
          {data.conclusion.focus && <p>{data.conclusion.focus}</p>}
          {data.conclusion.trend && <p>{data.conclusion.trend}</p>}
        </section>
      )}

    </div>
  );
}
