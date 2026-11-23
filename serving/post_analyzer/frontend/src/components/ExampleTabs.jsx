import { useState } from 'react'
import { LABEL_COLORS } from './LabelChart'

// Comment tiêu biểu theo từng nhãn (chọn nhãn bằng tab).
export default function ExampleTabs({ examples, conclusion }) {
  const labels = Object.keys(examples)
  const [active, setActive] = useState(labels.find((l) => examples[l].length) || labels[0])
  const list = examples[active] || []
  const note = conclusion?.by_label?.[active]
  return (
    <div>
      <div className="chips">
        {labels.map((l) => (
          <button key={l} className={`chip ${l === active ? 'active' : ''}`} onClick={() => setActive(l)}>
            <i className="dot" style={{ background: LABEL_COLORS[l] }} />{l} ({examples[l].length})
          </button>
        ))}
      </div>
      {note && <p className="summary">{note}</p>}
      {list.length ? (
        <ul className="examples">{list.map((t, i) => <li key={i}>{t}</li>)}</ul>
      ) : (
        <p className="muted">Không có comment cấp 1 nào mang nhãn này.</p>
      )}
    </div>
  )
}
