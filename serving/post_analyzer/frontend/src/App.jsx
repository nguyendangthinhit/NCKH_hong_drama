import { useCallback, useEffect, useState } from 'react'
import { createJob, getJob, getResult, listJobs } from './api'
import Dashboard from './components/Dashboard'
import JobList from './components/JobList'
import JobProgress from './components/JobProgress'
import SubmitForm from './components/SubmitForm'

const POLL_MS = 3000

// Job đang xem nằm trên URL (?job=<id>) để tải lại trang / chia sẻ link vẫn mở đúng.
const jobFromUrl = () => new URLSearchParams(window.location.search).get('job')

export default function App() {
  const [jobId, setJobId] = useState(jobFromUrl)
  const [job, setJob] = useState(null)
  const [view, setView] = useState(null)
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')

  const open = useCallback((id) => {
    window.history.pushState({}, '', id ? `?job=${id}` : window.location.pathname)
    setJobId(id); setJob(null); setView(null); setError('')
  }, [])

  useEffect(() => {
    const onPop = () => { setJobId(jobFromUrl()); setJob(null); setView(null) }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    if (!jobId) listJobs().then(setJobs).catch((e) => setError(e.message))
  }, [jobId])

  // Hỏi trạng thái job tới khi xong/lỗi; xong thì tải dữ liệu dashboard.
  useEffect(() => {
    if (!jobId) return undefined
    let stopped = false
    let timer
    const tick = async () => {
      try {
        const j = await getJob(jobId)
        if (stopped) return
        setJob(j); setError('')
        if (j.status === 'done') {
          const v = await getResult(jobId)
          if (!stopped) setView(v) // đã chuyển sang job khác thì bỏ kết quả cũ
          return
        }
        if (j.status === 'failed') return
      } catch (e) {
        if (stopped) return
        setError(e.message)
        if (e.status && e.status !== 503) return // 404/409/500: hỏi lại cũng không đổi
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS)
    }
    tick()
    return () => { stopped = true; clearTimeout(timer) }
  }, [jobId])

  async function retry() {
    try {
      const j = await createJob(job.url, job.max_comments, true)
      open(j.id)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => open(null)}>Phân tích bài viết</button>
        <span className="muted small">Cào comment → phân tích LLM → dashboard</span>
      </header>
      <main>
        {error && <p className="error">{error}</p>}
        {!jobId && (
          <>
            <SubmitForm onCreated={open} />
            <JobList jobs={jobs} onOpen={open} />
          </>
        )}
        {jobId && (
          <>
            <button className="link back" onClick={() => open(null)}>← Phân tích link khác</button>
            {view ? <Dashboard view={view} /> : job ? <JobProgress job={job} onRetry={retry} /> : <p className="muted">Đang tải…</p>}
          </>
        )}
      </main>
    </div>
  )
}
