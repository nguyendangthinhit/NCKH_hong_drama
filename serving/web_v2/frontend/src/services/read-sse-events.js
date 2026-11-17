export class SseProtocolError extends Error {}

// Network chunks không trùng ranh giới ký tự UTF-8, dòng hoặc sự kiện SSE.
export async function* readSseEvents(body, onActivity = () => {}) {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '';
  let event = 'message';
  let data = [];
  let size = 0;
  let ended = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      ended = done;
      if (value?.length) onActivity();
      try { buffer += decoder.decode(value, { stream: !done }); }
      catch { throw new SseProtocolError('Invalid UTF-8'); }
      let index;
      while ((index = buffer.search(/[\r\n]/)) !== -1) {
        if (buffer[index] === '\r' && index === buffer.length - 1 && !done) break;
        const line = buffer.slice(0, index);
        const width = buffer[index] === '\r' && buffer[index + 1] === '\n' ? 2 : 1;
        buffer = buffer.slice(index + width);
        if (!line) {
          if (data.length) yield { event, data: data.join('\n') };
          event = 'message'; data = []; size = 0;
        } else if (!line.startsWith(':')) {
          const colon = line.indexOf(':');
          const field = colon < 0 ? line : line.slice(0, colon);
          const content = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (field === 'event') event = content || 'message';
          if (field === 'data') { data.push(content); size += content.length; }
        }
        if (size > 65536) throw new SseProtocolError('Event too large');
      }
      if (buffer.length > 65536) throw new SseProtocolError('Line too large');
      if (done) {
        if (buffer || data.length) throw new SseProtocolError('Incomplete event');
        return;
      }
    }
  } finally {
    if (!ended) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
