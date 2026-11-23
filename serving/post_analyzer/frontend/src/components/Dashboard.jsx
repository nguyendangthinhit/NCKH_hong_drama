import { commentLabel } from '../estimate'
import ClusterList from './ClusterList'
import ExampleTabs from './ExampleTabs'
import LabelChart from './LabelChart'

function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {sub && <span className="muted small">{sub}</span>}
    </div>
  )
}

const pct = (n, d) => (d ? `${Math.round((n / d) * 100)}%` : '0%')

// Dashboard kết quả của 1 bài viết (dữ liệu từ GET /api/jobs/{id}/result).
export default function Dashboard({ view }) {
  const t = view.totals
  const labelTitle = view.domain === 'education' ? 'Quan điểm' : 'Cảm xúc'
  return (
    <div className="dashboard">
      <section className="card">
        <div className="row-between">
          <h2>{view.event_name || 'Bài viết'}</h2>
          <span className="badge badge-done">{view.domain_name}</span>
        </div>
        <a className="job-url" href={view.url} target="_blank" rel="noreferrer">{view.url}</a>
        {view.post_content && <p className="post-content">{view.post_content}</p>}
        {view.domain_info?.reason && <p className="muted small">Lĩnh vực do LLM đoán: {view.domain_info.reason}</p>}
      </section>

      <section className="stats">
        <Stat label="Comment đã phân tích" value={t.comments} sub={`yêu cầu ${commentLabel(view.max_comments)}`} />
        <Stat label="Cấp 1 / reply" value={`${t.top_level} / ${t.replies}`} />
        <Stat label="Cụm thảo luận" value={t.clusters} sub={`${t.controversial} cụm tranh cãi`} />
        <Stat label="Rác (bị lọc)" value={t.trash} sub={pct(t.trash, t.comments)} />
        {view.toxic && <Stat label="Độc hại" value={view.toxic.total} sub={pct(view.toxic.total, t.valid)} />}
      </section>

      <div className="grid-2">
        <section className="card">
          <h3>Phân bố {labelTitle.toLowerCase()} ({t.valid} comment hợp lệ)</h3>
          <LabelChart data={view.labels} />
        </section>
        {view.toxic ? (
          <section className="card">
            <h3>Loại nội dung độc hại</h3>
            {view.toxic.total ? <LabelChart data={view.toxic.by_type} nameKey="type" /> : <p className="muted">Không phát hiện comment độc hại.</p>}
          </section>
        ) : (
          <section className="card">
            <h3>Nhận định chung</h3>
            {view.conclusion?.focus && <p><strong>Trọng tâm:</strong> {view.conclusion.focus}</p>}
            {view.conclusion?.trend && <p><strong>Xu hướng:</strong> {view.conclusion.trend}</p>}
            {!view.conclusion?.focus && !view.conclusion?.trend && <p className="muted">LLM không trả về nhận định chung.</p>}
          </section>
        )}
      </div>

      <section className="card">
        <h3>Comment tiêu biểu theo {labelTitle.toLowerCase()}</h3>
        <ExampleTabs examples={view.examples} conclusion={view.conclusion} />
      </section>

      <section className="card">
        <h3>Các cụm thảo luận lớn nhất</h3>
        <ClusterList clusters={view.clusters} />
      </section>
    </div>
  )
}
