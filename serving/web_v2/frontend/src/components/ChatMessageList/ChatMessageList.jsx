// Danh sách tin nhắn của một cuộc trò chuyện; chưa có tin thì hiện màn hình chào + câu hỏi gợi ý.
import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { RobotOutlined } from '@ant-design/icons';
import styles from './ChatMessageList.module.scss';

const SUGGESTIONS = [
  'Top 5 sự kiện giáo dục được quan tâm nhất',
  'Drama showbiz nào đang được bàn tán nhiều?',
  'Dư luận nghĩ gì về vụ Shark Thủy nợ lương giáo viên?',
  'Bạn có thể giúp gì cho mình?',
];

function BotAvatar() {
  return (
    <div className={styles.avatar} aria-hidden="true">
      <RobotOutlined />
    </div>
  );
}

const MARKDOWN_COMPONENTS = {
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
  ),
};

function BotMessage({ text }) {
  // Agent nối nguồn ở cuối tin dưới dạng URL thuần. Chỉ tách khi cả phần này
  // là các URL hợp lệ để giữ nguyên nội dung Markdown khác của câu trả lời.
  const header = [...text.matchAll(/(?:^|\r?\n)[ \t]*Nguồn tin:[ \t]*(?:\r?\n|(?=https?:\/\/))/g)].at(-1);
  let body = text;
  let sources = [];
  if (header) {
    const urls = text.slice(header.index + header[0].length).trim().split(/\s+/);
    try {
      const parsed = urls.map((url) => new URL(url));
      if (parsed.every((url) => url.protocol === 'https:' || url.protocol === 'http:')) {
        body = text.slice(0, header.index).trimEnd();
        sources = [...new Set(urls)].map((url) => ({ url, host: new URL(url).hostname.replace(/^www\./, '') }));
      }
    } catch {
      // Nguồn không đúng định dạng: vẫn hiển thị đầy đủ văn bản gốc.
    }
  }

  return (
    <>
      <ReactMarkdown components={MARKDOWN_COMPONENTS}>{body}</ReactMarkdown>
      {sources.length > 0 && (
        <section className={styles.sources} aria-label="Nguồn tin">
          <p className={styles.sourcesTitle}>Nguồn tin</p>
          <ul className={styles.sourceList}>
            {sources.map(({ url, host }, index) => (
              <li key={url}>
                <a className={styles.sourceLink} href={url} target="_blank" rel="noopener noreferrer" title={url}>
                  <span>Nguồn {index + 1} · {host}</span>
                  <span aria-hidden="true">↗</span>
                  <span className={styles.srOnly}> (mở trong tab mới)</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

export default function ChatMessageList({ messages, pending, onSuggest }) {
  const endRef = useRef(null);

  // Cuộn xuống tin mới nhất mỗi khi có tin hoặc trạng thái chờ đổi.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, pending]);

  if (messages.length === 0 && !pending) {
    return (
      <div className={styles.welcome}>
        <div className={styles.welcomeIcon}><RobotOutlined /></div>
        <h1 className={styles.welcomeTitle}>Xin chào, mình là Hóng AI</h1>
        <p className={styles.welcomeText}>
          Hỏi mình về diễn biến các drama Giáo dục và Showbiz, phản ứng của dư luận
          hay những sự kiện đang được quan tâm nhất.
        </p>
        <div className={styles.suggestions}>
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className={styles.suggestion} onClick={() => onSuggest(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.list}>
      {messages.map((m, i) =>
        m.role === 'user' ? (
          <div key={i} className={styles.rowUser}>
            <div className={styles.bubbleUser}>{m.text}</div>
          </div>
        ) : (
          <div key={i} className={styles.rowBot}>
            <BotAvatar />
            <div className={`${styles.bubbleBot} ${m.error ? styles.bubbleError : ''}`}>
              <BotMessage text={m.text} />
            </div>
          </div>
        ),
      )}

      {pending && (
        <div className={styles.rowBot}>
          <BotAvatar />
          <div className={`${styles.bubbleBot} ${styles.typing}`} aria-label="Đang trả lời">
            <span /><span /><span />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
