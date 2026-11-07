// Worker HTTP: POST /chat {user_id|userId, message, source} -> {reply, intent, event_ids, timings_ms}; GET /health.
import { handleMessage } from "./chat-pipeline";
import { csv, Env } from "./env";
import { EVENTS } from "./event-store";
import { generate } from "./llm-client";
export { SessionStore } from "./session-durable-object";
import { emptySession, isSession, Session } from "./session-memory";

const MAX_BODY_BYTES = 8 * 1024;

const json = (body: unknown, status: number, cors: Record<string, string>): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors },
  });

/** So khoá theo thời gian hằng số (tránh lộ độ dài khớp qua thời gian phản hồi). */
async function keyMatches(given: string, expected: string): Promise<boolean> {
  const enc = new TextEncoder();
  const [a, b] = await Promise.all(
    [given, expected].map((s) => crypto.subtle.digest("SHA-256", enc.encode(s))),
  );
  const [x, y] = [new Uint8Array(a), new Uint8Array(b)];
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const origin = request.headers.get("Origin") ?? "";
    const originAllowed = csv(env.ALLOWED_ORIGINS).includes(origin);
    const cors: Record<string, string> = originAllowed
      ? {
          "Access-Control-Allow-Origin": origin,
          "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, X-Agent-Key",
          Vary: "Origin",
        }
      : {};
    const { pathname } = new URL(request.url);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (pathname === "/health" && request.method === "GET") {
      return json({ status: "ok", events: EVENTS.length }, 200, cors);
    }
    if (pathname !== "/chat" || request.method !== "POST") return json({ detail: "Not found" }, 404, cors);

    // Web (Origin được phép) gọi không cần khoá; n8n/ngoài web phải gửi đúng X-Agent-Key.
    if (!originAllowed) {
      const expected = env.AGENT_API_KEY ?? "";
      const given = request.headers.get("X-Agent-Key") ?? "";
      if (!expected || !(await keyMatches(given, expected))) {
        return json({ detail: "Sai hoặc thiếu X-Agent-Key" }, 401, cors);
      }
    }

    const text = await request.text();
    if (text.length > MAX_BODY_BYTES) return json({ detail: "Body quá lớn" }, 413, cors);
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(text);
    } catch {
      return json({ detail: "JSON không hợp lệ" }, 422, cors);
    }
    // Web gửi "userId", n8n/Messenger gửi "user_id": nhận cả hai.
    const userId = String(body.user_id ?? body.userId ?? "anonymous").slice(0, 128);
    // Không có khoá (web) thì luôn là "web": không cho chen vào phiên Messenger bằng cách tự khai source.
    const source = originAllowed ? "web" : String(body.source ?? "web").slice(0, 32);
    const message = body.message;
    if (typeof message !== "string" || message.length > 2000) {
      return json({ detail: "message phải là chuỗi tối đa 2000 ký tự" }, 422, cors);
    }

    try {
      const sessionId = `${source}:${userId}`;
      const doId = env.SESSIONS.idFromName(sessionId);
      let store = env.SESSIONS.get(doId);
      // Lỗi đọc phiên (vd. DO vừa khởi tạo sau deploy) thì dùng phiên rỗng, vẫn trả lời được.
      let loadFailed = false;
      const loaded = await store.load().catch((e) => {
        console.warn("Đọc phiên lỗi, dùng phiên rỗng:", (e as Error).message);
        loadFailed = true;
        return null;
      });
      const session = isSession(loaded) ? (loaded as Session) : emptySession(); // RPC làm mất kiểu tuple của Turn
      const result = await handleMessage(session, message, (sys, usr) => generate(env, sys, usr));
      // Ghi xong rồi mới trả lời: tin nhắn kế tiếp chắc chắn thấy lượt này (vài ms, cùng DO).
      // Lỗi ghi phiên không được làm hỏng câu trả lời.
      if (loadFailed) store = env.SESSIONS.get(doId); // stub đã ném lỗi có thể hỏng: tạo lại
      await store.record(message, result.reply, result.event_ids)
        .catch((e) => console.warn("Ghi phiên lỗi:", (e as Error).message));
      console.log(`user=${sessionId} intent=${result.intent} events=${result.event_ids} provider=${result.provider} timings=${JSON.stringify(result.timings_ms)}`);
      const { provider: _provider, ...publicResult } = result;
      return json(publicResult, 200, cors);
    } catch (e) {
      console.error("Lỗi xử lý /chat:", (e as Error).stack);
      return json({ detail: "Lỗi nội bộ" }, 500, cors);
    }
  },
};
