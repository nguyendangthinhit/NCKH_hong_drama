import { LABEL_COLORS } from './LabelChart'

// Các cụm thảo luận lớn nhất: comment gốc + tóm tắt LLM + phân bố nhãn trong cụm.
export default function ClusterList({ clusters }) {
  if (!clusters.length) return <p className="muted">Không có cụm thảo luận.</p>
  return (
    <ul className="clusters">
      {clusters.map((c) => {
        const total = Object.values(c.labels).reduce((s, n) => s + n, 0)
        return (
          <li key={c.root_id} className="cluster">
            <div className="row-between">
              <span className="muted">{c.size} comment trong cụm</span>
              {c.controversial && <span className="badge badge-failed">Tranh cãi</span>}
            </div>
            <p className="root-text">“{c.root_text || '(không có nội dung)'}”</p>
            {c.summary && <p className="summary">{c.summary}</p>}
            {total > 0 && (
              <div className="stack" title={Object.entries(c.labels).map(([k, v]) => `${k}: ${v}`).join(', ')}>
                {Object.entries(c.labels).map(([k, v]) => (
                  <div key={k} style={{ width: `${(v / total) * 100}%`, background: LABEL_COLORS[k] || '#4c8bf5' }} />
                ))}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
