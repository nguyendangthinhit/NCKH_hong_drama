// Nút nổi góc phải: bấm để mở trang chat lớn (/chat). Ẩn khi đang ở trang chat.
import { useLocation, useNavigate } from 'react-router-dom';
import styles from './Chatbot.module.scss';

const Chatbot = () => {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  if (pathname.startsWith('/chat')) return null;

  return (
    <button
      type="button"
      className={styles.launcher}
      onClick={() => navigate('/chat')}
      aria-label="Mở trợ lý Hóng AI"
    >
      <span className={styles.launcherIcon}>
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 3c5.5 0 10 3.58 10 8s-4.5 8-10 8c-1.24 0-2.43-.18-3.53-.5C5.55 21 2 21 2 21c2.33-2.33 2.7-3.9 2.75-4.5C3.05 15.07 2 13.13 2 11c0-4.42 4.5-8 10-8z" />
        </svg>
      </span>
      <span className={styles.launcherLabel}>Hỏi Hóng AI</span>
    </button>
  );
};

export default Chatbot;
