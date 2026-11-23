// Ước tính thời gian để người dùng chọn số comment. Số đo thật của dự án:
// - crawler: ~8 comment mỗi vòng bấm/cuộn, mỗi vòng ~6s (crawl_links_from_sheet.max_rounds_for)
// - LLM: 1 request / ~60 comment, ~2–3 phút / request (đo 2026-11-22 với deepseek)
const SECONDS_PER_ROUND = 6
const COMMENTS_PER_ROUND = 8
const MINUTES_PER_REQUEST = [2, 3]

export function commentLabel(n) {
  return n === 0 ? 'Toàn bộ' : `${n} comment`
}

export function estimate(maxComments, perRequest = 60) {
  if (maxComments === 0) {
    return { requests: null, text: 'Không ước tính trước được: tuỳ số comment Facebook cho tải (bài lớn có thể mất vài giờ).' }
  }
  const crawlMin = Math.max(1, Math.round((maxComments / COMMENTS_PER_ROUND) * SECONDS_PER_ROUND / 60))
  const requests = Math.ceil(maxComments / perRequest) + 1 // +1 request đoán lĩnh vực
  const [lo, hi] = MINUTES_PER_REQUEST.map((m) => crawlMin + requests * m)
  return { requests, text: `Khoảng ${requests} request LLM, mất chừng ${lo}–${hi} phút (cào ~${crawlMin} phút).` }
}

export function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
}
