// Gọi backend post_analyzer qua proxy /api của Vite (xem vite.config.js).
const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, options)
  } catch {
    throw new Error('Không kết nối được backend (đã chạy uvicorn cổng 8020 chưa?)')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || `Lỗi HTTP ${res.status}`)
    err.status = res.status // App dùng để dừng hỏi lại khi lỗi không tự hết (404/409/500)
    throw err
  }
  return data
}

export const getOptions = () => request('/api/options')
export const listJobs = () => request('/api/jobs')
export const getJob = (id) => request(`/api/jobs/${id}`)
export const getResult = (id) => request(`/api/jobs/${id}/result`)
export const createJob = (url, maxComments, force = false) =>
  request('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, max_comments: maxComments, force }),
  })
