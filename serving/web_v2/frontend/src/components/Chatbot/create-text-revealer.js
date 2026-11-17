const WORD_INTERVAL_MS = 32;

// Tốc độ hiển thị độc lập với kích thước chunk mà provider gửi về.
export default function createTextRevealer(onText, {
  scheduleFrame = requestAnimationFrame,
  cancelFrame = cancelAnimationFrame,
} = {}) {
  const word = /\s*\S+\s*|\s+/uy;
  let buffer = '';
  let position = 0;
  let frame = null;
  let nextAt = 0;
  let ended = false;
  let cancelled = false;
  let completion;
  let resolveCompletion;
  let rejectCompletion;

  const abortError = () => new DOMException('Aborted', 'AbortError');

  function schedule() {
    if (frame === null && !cancelled && position < buffer.length) {
      frame = scheduleFrame(tick);
    }
  }

  function tick(timestamp) {
    frame = null;
    if (cancelled) return;
    if (timestamp >= nextAt && position < buffer.length) {
      // Chỉ đọc từ vị trí mới, không tách lại toàn bộ câu trả lời mỗi frame.
      word.lastIndex = position;
      word.exec(buffer);
      position = word.lastIndex;
      onText(buffer.slice(0, position));
      nextAt = timestamp + WORD_INTERVAL_MS;
    }
    if (position < buffer.length) schedule();
    else if (ended) resolveCompletion?.();
  }

  return {
    push(text) {
      if (cancelled || ended || !text) return;
      buffer += text;
      schedule();
    },
    finish() {
      if (cancelled) return Promise.reject(abortError());
      ended = true;
      if (position === buffer.length) return Promise.resolve();
      completion ??= new Promise((resolve, reject) => {
        resolveCompletion = resolve;
        rejectCompletion = reject;
      });
      // done chỉ kết thúc nhận dữ liệu; phần còn trong bộ đệm vẫn nhả từng từ.
      schedule();
      return completion;
    },
    cancel() {
      if (cancelled) return;
      cancelled = true;
      if (frame !== null) cancelFrame(frame);
      frame = null;
      rejectCompletion?.(abortError());
    },
  };
}
