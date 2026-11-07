// Thanh lịch sử chat: tạo cuộc mới, chọn / xoá cuộc cũ. Trên điện thoại hiện dạng ngăn kéo (open/onClose).
import { DeleteOutlined, PlusOutlined, MessageOutlined, CloseOutlined } from '@ant-design/icons';
import { useChatHistory } from '../../context/ChatHistoryContext';
import styles from './ChatHistorySidebar.module.scss';

function formatTime(ts) {
  const d = new Date(ts);
  const sameDay = d.toDateString() === new Date().toDateString();
  return sameDay
    ? d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
}

export default function ChatHistorySidebar({ open, onClose }) {
  const { conversations, activeConversation, startNew, select, remove, clearAll, isPending } = useChatHistory();

  const pick = (fn) => (...args) => {
    fn(...args);
    onClose?.();
  };

  return (
    <>
      <div className={`${styles.backdrop} ${open ? styles.backdropOpen : ''}`} onClick={onClose} />
      <aside className={`${styles.sidebar} ${open ? styles.sidebarOpen : ''}`} aria-label="Lịch sử trò chuyện">
        <div className={styles.top}>
          <button type="button" className={styles.newBtn} onClick={pick(startNew)}>
            <PlusOutlined /> Cuộc trò chuyện mới
          </button>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Đóng lịch sử">
            <CloseOutlined />
          </button>
        </div>

        <div className={styles.sectionTitle}>Lịch sử</div>

        <div className={styles.list}>
          {conversations.length === 0 && (
            <p className={styles.empty}>Chưa có cuộc trò chuyện nào. Hãy đặt câu hỏi đầu tiên!</p>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`${styles.item} ${activeConversation?.id === c.id ? styles.itemActive : ''}`}
            >
              <button type="button" className={styles.itemMain} onClick={pick(() => select(c.id))}>
                <MessageOutlined className={styles.itemIcon} />
                <span className={styles.itemText}>
                  <span className={styles.itemTitle}>{c.title}</span>
                  <span className={styles.itemMeta}>
                    {isPending(c.id) ? 'Đang trả lời…' : `${c.messages.length} tin · ${formatTime(c.updatedAt)}`}
                  </span>
                </span>
              </button>
              <button
                type="button"
                className={styles.deleteBtn}
                onClick={() => remove(c.id)}
                aria-label={`Xoá cuộc trò chuyện ${c.title}`}
              >
                <DeleteOutlined />
              </button>
            </div>
          ))}
        </div>

        <div className={styles.footer}>
          {conversations.length > 0 && (
            <button type="button" className={styles.clearBtn} onClick={clearAll}>
              Xoá toàn bộ lịch sử
            </button>
          )}
          <p className={styles.note}>Lịch sử chỉ lưu tạm trên trang này, tải lại trang sẽ mất.</p>
        </div>
      </aside>
    </>
  );
}
