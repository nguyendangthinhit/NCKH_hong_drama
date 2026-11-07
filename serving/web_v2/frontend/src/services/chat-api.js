// Gọi agent chatbot (Cloudflare Worker / serving/chat_agent). URL đặt qua VITE_CHAT_API_URL.
const CHAT_URL = import.meta.env.VITE_CHAT_API_URL || 'http://127.0.0.1:8010/chat';
const REQUEST_TIMEOUT_MS = 30000;

// Id trình duyệt lưu trong cookie 1 năm; khi có đăng nhập sẽ thay bằng id tài khoản.
export function getOrCreateBrowserId() {
  const match = document.cookie.split(';').map((c) => c.trim()).find((c) => c.startsWith('userId='));
  if (match) return decodeURIComponent(match.slice('userId='.length));
  const newId = crypto.randomUUID();
  document.cookie = `userId=${newId}; path=/; max-age=31536000`;
  return newId;
}

// Gửi 1 tin nhắn. sessionId tách theo cuộc trò chuyện để agent không nhớ lẫn ngữ cảnh giữa các cuộc.
export async function sendChatMessage(sessionId, message) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(CHAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: sessionId, message, source: 'web' }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Agent trả mã ${res.status}`);
    const data = await res.json();
    const result = Array.isArray(data) ? data[0] : data;
    return result?.reply || 'Không có phản hồi.';
  } finally {
    clearTimeout(timer);
  }
}
