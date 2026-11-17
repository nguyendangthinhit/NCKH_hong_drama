import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatApiError, getOrCreateBrowserId, streamChatMessage } from '../../services/chat-api';
import createTextRevealer from './create-text-revealer';

export default function useChatbotStream() {
  const [messages, setMessages] = useState([{
    id: 'welcome', type: 'bot', text: 'Chào bạn, đây là hệ thống chatbot. Tôi có thể giúp gì cho bạn?',
  }]);
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const request = useRef(null);
  const mounted = useRef(true);
  const sequence = useRef(0);
  useEffect(() => {
    mounted.current = true;
    const abort = () => request.current?.abort();
    // Điều hướng cả trang/BFCache không nhất thiết gọi cleanup của React.
    window.addEventListener('pagehide', abort);
    return () => {
      mounted.current = false;
      abort();
      window.removeEventListener('pagehide', abort);
    };
  }, []);

  const send = useCallback(async (message) => {
    const text = message.trim();
    if (!text || inFlight.current) return;
    inFlight.current = true;
    const id = String(++sequence.current);
    const botId = `bot-${id}`;
    const controller = new AbortController();
    request.current = controller;
    let displayed = '';
    const paint = (error) => {
      if (mounted.current) setMessages((previous) => previous.map((item) => (
        item.id === botId ? { ...item, text: displayed, error } : item
      )));
    };
    const revealer = createTextRevealer((visible) => {
      displayed = visible;
      paint();
    });
    const stopRevealing = () => revealer.cancel();
    controller.signal.addEventListener('abort', stopRevealing, { once: true });
    setMessages((previous) => [...previous,
      { id: `user-${id}`, type: 'user', text }, { id: botId, type: 'bot', text: '' },
    ]);
    setLoading(true);
    try {
      let failure;
      await streamChatMessage(getOrCreateBrowserId(), text, {
        signal: controller.signal,
        onDelta: revealer.push,
      }).catch((error) => { failure = error; });
      // done/lỗi mạng không làm bung cả bộ đệm ra; chờ hiển thị hết phần đã nhận.
      await revealer.finish();
      if (failure) throw failure;
    } catch (error) {
      if (mounted.current) paint(controller.signal.aborted
        ? 'Câu trả lời đã dừng trước khi hoàn tất.'
        : error instanceof ChatApiError ? error.message : 'Đã xảy ra lỗi khi gửi tin nhắn. Vui lòng thử lại.');
    } finally {
      revealer.cancel();
      controller.signal.removeEventListener('abort', stopRevealing);
      request.current = null;
      inFlight.current = false;
      if (mounted.current) setLoading(false);
    }
  }, []);

  return { messages, loading, send };
}
