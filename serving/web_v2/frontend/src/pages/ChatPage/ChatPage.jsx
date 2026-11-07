// Trang chat lớn (/chat): sidebar lịch sử bên trái, khung hội thoại + ô nhập bên phải.
import { useRef, useState } from 'react';
import { MenuOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons';
import ChatHistorySidebar from '../../components/ChatHistorySidebar/ChatHistorySidebar';
import ChatMessageList from '../../components/ChatMessageList/ChatMessageList';
import { useChatHistory } from '../../context/ChatHistoryContext';
import styles from './ChatPage.module.scss';

const INPUT_MAX_HEIGHT = 160;

export default function ChatPage() {
  const { activeConversation, send, startNew, isPending } = useChatHistory();
  const [input, setInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const inputRef = useRef(null);

  const messages = activeConversation?.messages || [];
  const pending = activeConversation ? isPending(activeConversation.id) : false;

  // Ô nhập tự giãn theo nội dung, tối đa INPUT_MAX_HEIGHT.
  const resizeInput = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, INPUT_MAX_HEIGHT)}px`;
  };

  const submit = (text = input) => {
    if (!text.trim() || pending) return;
    send(text);
    setInput('');
    requestAnimationFrame(resizeInput);
    inputRef.current?.focus();
  };

  const onKeyDown = (e) => {
    // Enter gửi, Shift+Enter xuống dòng; bỏ qua khi đang gõ tiếng Việt (IME composing).
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={styles.page}>
      <ChatHistorySidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <section className={styles.main}>
        <header className={styles.topbar}>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => setSidebarOpen(true)}
            aria-label="Mở lịch sử"
          >
            <MenuOutlined />
          </button>
          <div className={styles.topbarTitle}>
            <h2>{activeConversation?.title || 'Cuộc trò chuyện mới'}</h2>
            <span>Hóng AI · Trợ lý drama Giáo dục & Showbiz</span>
          </div>
          <button type="button" className={styles.iconBtn} onClick={startNew} aria-label="Cuộc trò chuyện mới">
            <PlusOutlined />
          </button>
        </header>

        <div className={styles.scroll}>
          <ChatMessageList messages={messages} pending={pending} onSuggest={submit} />
        </div>

        <div className={styles.composerWrap}>
          <div className={styles.composer}>
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              placeholder="Hỏi về một drama, nhân vật hay phản ứng dư luận…"
              onChange={(e) => {
                setInput(e.target.value);
                resizeInput();
              }}
              onKeyDown={onKeyDown}
              maxLength={2000}
              aria-label="Nội dung tin nhắn"
            />
            <button
              type="button"
              className={styles.sendBtn}
              onClick={() => submit()}
              disabled={!input.trim() || pending}
              aria-label="Gửi"
            >
              <SendOutlined />
            </button>
          </div>
          <p className={styles.hint}>
            Enter để gửi, Shift + Enter để xuống dòng. Câu trả lời dựa trên dữ liệu hệ thống đã thu thập.
          </p>
        </div>
      </section>
    </div>
  );
}
