import { commentLabel } from '../estimate'
import StatusBadge from './StatusBadge'

const STEPS = [
  ['queued', 'Chờ tới lượt'],
  ['crawling', 'Cào comment'],
  ['analyzing', 'Phân tích LLM'],
  ['done', 'Tổng hợp'],
]

// Tiến độ của job đang chạy (trang tự hỏi lại backend mỗi vài giây).
export default function JobProgress({ job, onRetry }) {
  const current = STEPS.findIndex(([s]) => s === job.status)
  const pct = job.progress_total ? Math.round((job.progress_done / job.progress_total) * 100) : 0
  return (
    <section className="card">
      <div className="row-between">
        <h2>Đang xử lý bài viết</h2>
        <StatusBadge status={job.status} />
      </div>
      <p className="job-url" title={job.url}>{job.url}</p>
      <p className="muted">Số comment yêu cầu: {commentLabel(job.max_comments)}
        {job.n_comments ? ` · đã cào được ${job.n_comments}` : ''}
        {job.domain_info ? ` · lĩnh vực: ${job.domain === 'education' ? 'Giáo dục' : 'Showbiz'}` : ''}</p>

      {job.status === 'failed' ? (
        <div className="error-box">
          <strong>Không hoàn thành được.</strong>
          <p>{job.error}</p>
          <button className="primary" onClick={onRetry}>Gửi lại link này</button>
        </div>
      ) : (
        <>
          <ol className="steps">
            {STEPS.map(([s, name], i) => (
              <li key={s} className={i < current ? 'done' : i === current ? 'current' : ''}>{name}</li>
            ))}
          </ol>
          <p>{job.status === 'queued' && job.queue_position
            ? `Có ${job.queue_position} bài đang chạy hoặc chờ phía trước.`
            : job.stage}</p>
          {job.status === 'analyzing' && job.progress_total > 0 && (
            <div className="bar"><div style={{ width: `${pct}%` }} /></div>
          )}
          <p className="hint">Có thể đóng trang này; job vẫn chạy trên máy chủ và kết quả lưu lại ở "Các lần phân tích gần đây".</p>
        </>
      )}
    </section>
  )
}
