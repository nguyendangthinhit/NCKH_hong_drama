const NAMES = {
  queued: 'Đang chờ',
  crawling: 'Đang cào',
  analyzing: 'Đang phân tích',
  done: 'Xong',
  failed: 'Lỗi',
}

export default function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{NAMES[status] || status}</span>
}
