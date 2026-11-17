import { readSseEvents, SseProtocolError } from './read-sse-events';

const CHAT_API_URL = import.meta.env.VITE_CHAT_API_URL?.trim()
  || 'http://127.0.0.1:8010/chat';
const CHAT_STREAM_API_URL = import.meta.env.VITE_CHAT_STREAM_API_URL?.trim()
  || `${CHAT_API_URL.replace(/\/+$/, '')}/stream`;

export const CHAT_MESSAGE_LIMIT = 2000;
// Agent có thể thử nhiều khóa/provider, mỗi lần mặc định chờ tối đa 6 giây.
const CHAT_TIMEOUT_MS = 35000;
const FIRST_DELTA_TIMEOUT_MS = 60000;
const INVALID_REPLY = 'Chatbot trả về phản hồi không hợp lệ. Vui lòng thử lại.';

export class ChatApiError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ChatApiError';
  }
}

// Giữ ID trình duyệt dùng chung với lịch sử chat; không đổi giữa các lượt hỏi.
export function getOrCreateBrowserId() {
  const match = document.cookie.split(';').map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith('userId='));
  if (match) return decodeURIComponent(match.slice('userId='.length));
  const newId = crypto.randomUUID();
  document.cookie = `userId=${newId}; path=/; max-age=31536000`;
  return newId;
}

function messageBody(sessionId, message) {
  const text = typeof message === 'string' ? message.trim() : '';
  if (!text || text.length > CHAT_MESSAGE_LIMIT) {
    throw new ChatApiError('Vui lòng nhập tin nhắn từ 1 đến 2.000 ký tự.');
  }
  return JSON.stringify({ message: text, userId: sessionId, source: 'web' });
}

function checkStatus(response) {
  if (response.ok) return;
  if (response.status === 422) {
    throw new ChatApiError('Tin nhắn không hợp lệ hoặc vượt quá giới hạn cho phép.');
  }
  if (response.status === 401 || response.status === 403) {
    throw new ChatApiError('Không thể truy cập chatbot. Vui lòng thử lại sau.');
  }
  throw new ChatApiError('Chatbot đang gặp sự cố. Vui lòng thử lại sau.');
}

// Giữ nguyên API JSON và thứ tự tham số cho ChatHistoryContext.
export async function sendChatMessage(sessionId, message) {
  const body = messageBody(sessionId, message);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

  try {
    const response = await fetch(CHAT_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      signal: controller.signal,
    });

    checkStatus(response);

    let data;
    try {
      data = await response.json();
    } catch (error) {
      if (controller.signal.aborted) throw error;
      throw new ChatApiError(INVALID_REPLY);
    }
    if (!data || Array.isArray(data) || typeof data.reply !== 'string' || !data.reply.trim()) {
      throw new ChatApiError(INVALID_REPLY);
    }
    return data.reply;
  } catch (error) {
    if (error instanceof ChatApiError) throw error;
    if (controller.signal.aborted || error?.name === 'AbortError') {
      throw new ChatApiError('Chatbot phản hồi quá lâu. Vui lòng thử lại.');
    }
    throw new ChatApiError('Không thể kết nối chatbot. Vui lòng thử lại sau.');
  } finally {
    clearTimeout(timeout);
  }
}

export async function streamChatMessage(sessionId, message, { onDelta, signal } = {}) {
  const body = messageBody(sessionId, message);
  const controller = new AbortController();
  let timer;
  let timedOut = false;
  let metadata;
  let hasText = false;
  const abort = () => controller.abort();
  // Giới hạn thời gian im lặng, không giới hạn tổng thời gian của một stream đang chạy.
  const armTimeout = () => {
    clearTimeout(timer);
    timer = setTimeout(() => { timedOut = true; controller.abort(); }, hasText ? CHAT_TIMEOUT_MS : FIRST_DELTA_TIMEOUT_MS);
  };
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  try {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    armTimeout();
    const response = await fetch(CHAT_STREAM_API_URL, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body, signal: controller.signal,
    });
    checkStatus(response);
    if (!response.body || !response.headers.get('Content-Type')?.includes('text/event-stream')) {
      throw new ChatApiError(INVALID_REPLY);
    }
    for await (const frame of readSseEvents(response.body, armTimeout)) {
      let data;
      try { data = JSON.parse(frame.data); } catch { throw new ChatApiError(INVALID_REPLY); }
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new ChatApiError(INVALID_REPLY);
      switch (frame.event) {
        case 'meta':
          if (metadata || typeof data.intent !== 'string' || !Array.isArray(data.event_ids)) throw new ChatApiError(INVALID_REPLY);
          metadata = data;
          break;
        case 'delta':
          if (!metadata || typeof data.text !== 'string') throw new ChatApiError(INVALID_REPLY);
          if (data.text) { hasText = true; armTimeout(); onDelta?.(data.text); }
          break;
        case 'done':
          if (!metadata || !hasText) throw new ChatApiError(INVALID_REPLY);
          return { ...metadata, ...data };
        case 'error':
          throw new ChatApiError((typeof data.message === 'string' && data.message.trim()) || 'Câu trả lời bị gián đoạn. Bạn thử lại nhé.');
        default:
          throw new ChatApiError(INVALID_REPLY);
      }
    }
    throw new ChatApiError('Câu trả lời bị gián đoạn. Bạn thử gửi lại nhé.');
  } catch (error) {
    if (timedOut) throw new ChatApiError('Chatbot phản hồi quá lâu. Vui lòng thử lại.');
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (error instanceof ChatApiError) throw error;
    if (error instanceof SseProtocolError) throw new ChatApiError(INVALID_REPLY);
    throw new ChatApiError('Không thể kết nối chatbot. Vui lòng thử lại sau.');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}
