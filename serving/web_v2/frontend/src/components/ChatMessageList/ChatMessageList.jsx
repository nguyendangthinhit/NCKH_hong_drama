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
              <ReactMarkdown>{m.text}</ReactMarkdown>
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
