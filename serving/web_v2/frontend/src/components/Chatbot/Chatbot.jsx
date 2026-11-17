import React, { memo, useLayoutEffect, useRef, useState } from 'react';
import styles from './Chatbot.module.scss';
import ReactMarkdown from 'react-markdown';
import { CHAT_MESSAGE_LIMIT } from '../../services/chat-api';
import useChatbotStream from './use-chatbot-stream';

// Các tin đã hoàn tất không cần parse lại Markdown khi tin mới đang stream.
const ChatMessage = memo(function ChatMessage({ message: msg }) {
  return (
    <div className={msg.type === 'bot' ? styles.messageRowBot : styles.messageRowUser}>
      {msg.type === 'bot' && <div className={styles.avatarBot}>🤖</div>}
      <div className={msg.type === 'bot' ? styles.bubbleBot : styles.bubbleUser}>
        {msg.type === 'bot' ? <>
          <ReactMarkdown>{msg.text || msg.error || 'Đang trả lời...'}</ReactMarkdown>
          {msg.text && msg.error && <p role="status">{msg.error}</p>}
        </> : msg.text}
      </div>
    </div>
  );
});

const Chatbot = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { messages, loading, send } = useChatbotStream();
  const [input, setInput] = useState('');
  const body = useRef(null);
  const followBottom = useRef(true);
  useLayoutEffect(() => {
    if (followBottom.current && body.current) body.current.scrollTop = body.current.scrollHeight;
  }, [messages, isOpen]);

  // Gửi câu hỏi tới agent, giữ nguyên userId để nối tiếp ngữ cảnh hội thoại.
  const sendMessage = () => {
    const message = input.trim();
    if (!message || loading) return;

    followBottom.current = true;
    setInput('');
    void send(message);
  };

  return (
    <div className={styles.chatbotContainer}>
      <div className={`${styles.chatWindow} ${isOpen ? styles.open : ''}`}>
        
        {/* HEADER */}
        <div className={styles.chatHeader}>
          <h4>Chat Hỗ Trợ</h4>
          <button
            className={styles.closeBtn}
            onClick={() => setIsOpen(false)}
          >
            &times;
          </button>
        </div>

        {/* BODY */}
        <div className={styles.chatBody} ref={body} onScroll={() => {
          const element = body.current;
          followBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
        }}>
          {messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)}

        </div>

        {/* FOOTER */}
        <div className={styles.chatFooter}>
          <input
            type="text"
            placeholder="Nhập tin nhắn..."
            className={styles.chatInput}
            value={input}
            maxLength={CHAT_MESSAGE_LIMIT}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !loading && sendMessage()}
            disabled={loading}
          />
          <button className={styles.sendBtn} onClick={sendMessage} disabled={loading}>
            Gửi
          </button>
        </div>
      </div>

      {/* FLOATING BUTTON */}
      <button
        className={styles.floatingBtn}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? (
          <span className={styles.closeIcon}>&times;</span>
        ) : (
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            className={styles.chatIcon}
          >
            <path d="M12 3c5.5 0 10 3.58 10 8s-4.5 8-10 8c-1.24 0-2.43-.18-3.53-.5C5.55 21 2 21 2 21c2.33-2.33 2.7-3.9 2.75-4.5C3.05 15.07 2 13.13 2 11c0-4.42 4.5-8 10-8z" />
          </svg>
        )}
      </button>
    </div>
  );
};

export default Chatbot;
