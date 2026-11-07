// Lịch sử chat giữ trong bộ nhớ (React state): còn khi chuyển trang, mất khi reload.
// Khi có đăng nhập + DB, thay phần lưu trong reducer bằng API theo người dùng; giao diện giữ nguyên hook useChatHistory().
import { createContext, useCallback, useContext, useMemo, useReducer } from 'react';
import { getOrCreateBrowserId, sendChatMessage } from '../services/chat-api';

const ChatHistoryContext = createContext(null);
const TITLE_MAX = 48;

const initialState = { conversations: [], activeId: null, pendingIds: [] };

function makeTitle(text) {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length > TITLE_MAX ? `${clean.slice(0, TITLE_MAX)}…` : clean;
}

function reducer(state, action) {
  switch (action.type) {
    case 'create':
      return {
        ...state,
        activeId: action.conversation.id,
        conversations: [action.conversation, ...state.conversations],
      };
    case 'append': {
      // Thêm tin rồi đẩy cuộc trò chuyện lên đầu danh sách.
      const target = state.conversations.find((c) => c.id === action.id);
      if (!target) return state;
      const updated = { ...target, messages: [...target.messages, action.message], updatedAt: action.message.ts };
      return { ...state, conversations: [updated, ...state.conversations.filter((c) => c.id !== action.id)] };
    }
    case 'pending':
      return {
        ...state,
        pendingIds: action.value
          ? [...state.pendingIds, action.id]
          : state.pendingIds.filter((id) => id !== action.id),
      };
    case 'select':
      return { ...state, activeId: action.id };
    case 'remove':
      return {
        ...state,
        activeId: state.activeId === action.id ? null : state.activeId,
        conversations: state.conversations.filter((c) => c.id !== action.id),
      };
    case 'clear':
      return { ...initialState, pendingIds: state.pendingIds };
    default:
      return state;
  }
}

export function ChatHistoryProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Gửi tin: chưa có cuộc trò chuyện đang mở thì tạo mới. Request chạy trong context nên
  // người dùng rời trang chat giữa chừng thì câu trả lời vẫn được lưu.
  const send = useCallback(async (text) => {
    const message = text.trim();
    if (!message) return;
    let id = state.activeId;
    const now = Date.now();
    if (!id) {
      id = crypto.randomUUID();
      dispatch({ type: 'create', conversation: { id, title: makeTitle(message), createdAt: now, updatedAt: now, messages: [] } });
    }
    dispatch({ type: 'append', id, message: { role: 'user', text: message, ts: now } });
    dispatch({ type: 'pending', id, value: true });
    try {
      const reply = await sendChatMessage(`${getOrCreateBrowserId()}:${id}`, message);
      dispatch({ type: 'append', id, message: { role: 'bot', text: reply, ts: Date.now() } });
    } catch {
      dispatch({
        type: 'append',
        id,
        message: { role: 'bot', text: 'Không kết nối được chatbot. Bạn thử gửi lại sau nhé.', ts: Date.now(), error: true },
      });
    } finally {
      dispatch({ type: 'pending', id, value: false });
    }
  }, [state.activeId]);

  const value = useMemo(() => ({
    conversations: state.conversations,
    activeConversation: state.conversations.find((c) => c.id === state.activeId) || null,
    isPending: (id) => state.pendingIds.includes(id),
    send,
    startNew: () => dispatch({ type: 'select', id: null }),
    select: (id) => dispatch({ type: 'select', id }),
    remove: (id) => dispatch({ type: 'remove', id }),
    clearAll: () => dispatch({ type: 'clear' }),
  }), [state, send]);

  return <ChatHistoryContext.Provider value={value}>{children}</ChatHistoryContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChatHistory() {
  const ctx = useContext(ChatHistoryContext);
  if (!ctx) throw new Error('useChatHistory phải dùng bên trong ChatHistoryProvider');
  return ctx;
}
