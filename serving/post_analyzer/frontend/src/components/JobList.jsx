import { commentLabel, formatTime } from '../estimate'
import StatusBadge from './StatusBadge'

// Danh sách các lần phân tích gần đây (bấm để mở).
export default function JobList({ jobs, onOpen }) {
  if (!jobs.length) return null
  return (
    <section className="card">
      <h3>Các lần phân tích gần đây</h3>
      <ul className="job-list">
        {jobs.map((j) => (
          <li key={j.id}>
            <button className="job-row" onClick={() => onOpen(j.id)}>
              <StatusBadge status={j.status} />
              <span className="job-url" title={j.url}>{j.url}</span>
              <span className="muted">{commentLabel(j.max_comments)} · {formatTime(j.created_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
