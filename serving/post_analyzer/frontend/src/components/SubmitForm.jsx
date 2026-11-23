import { useEffect, useState } from 'react'
import { createJob, getOptions } from '../api'
import { commentLabel, estimate } from '../estimate'

const FALLBACK_CHOICES = [50, 100, 200, 300, 400, 500, 0]

// Form dán link Facebook + chọn số comment muốn thu thập.
export default function SubmitForm({ onCreated }) {
  const [url, setUrl] = useState('')
  const [choices, setChoices] = useState(FALLBACK_CHOICES)
  const [perRequest, setPerRequest] = useState(60)
  const [maxComments, setMaxComments] = useState(50)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reused, setReused] = useState(null)

  useEffect(() => {
    getOptions()
      .then((o) => { setChoices(o.comment_choices); setPerRequest(o.comments_per_request) })
      .catch(() => {})
  }, [])

  async function submit(e, force = false) {
    e?.preventDefault()
    setBusy(true); setError(''); setReused(null)
    try {
      const job = await createJob(url, maxComments, force)
      if (job.reused && job.status === 'done') setReused(job)
      else onCreated(job.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const est = estimate(maxComments, perRequest)
  return (
    <form className="card form" onSubmit={submit}>
      <h2>Phân tích một bài viết Facebook</h2>
      <label className="field">
        <span>Link bài viết</span>
        <input type="url" required placeholder="https://www.facebook.com/.../posts/..." value={url}
          onChange={(e) => setUrl(e.target.value)} />
      </label>
      <div className="field">
        <span>Bạn chọn số comment muốn thu thập về</span>
        <div className="chips">
          {choices.map((n) => (
            <button type="button" key={n} className={`chip ${n === maxComments ? 'active' : ''}`}
              onClick={() => setMaxComments(n)}>
              {commentLabel(n)}{n === 50 ? ' (gợi ý)' : ''}
            </button>
          ))}
        </div>
        <p className="hint">{est.text}</p>
      </div>
      {error && <p className="error">{error}</p>}
      {reused && (
        <div className="notice">
          Link này đã được phân tích với {commentLabel(reused.max_comments)}.
          <button type="button" className="link" onClick={() => onCreated(reused.id)}>Xem kết quả cũ</button>
          <button type="button" className="link" disabled={busy} onClick={(e) => submit(e, true)}>Cào và phân tích lại</button>
        </div>
      )}
      <button className="primary" disabled={busy || !url}>{busy ? 'Đang gửi…' : 'Bắt đầu phân tích'}</button>
    </form>
  )
}
