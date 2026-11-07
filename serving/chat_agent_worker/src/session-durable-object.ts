// Durable Object giữ phiên chat: mỗi phiên ("source:userId") một instance, đọc ngay thấy lượt vừa ghi
// (KV nhất quán sau nên câu hỏi nối tiếp gửi nhanh từng đọc phải phiên cũ).
import { DurableObject } from "cloudflare:workers";
import { emptySession, nextSession, Session, SESSION_TTL_MS } from "./session-memory";

const STATE_KEY = "session";

export class SessionStore extends DurableObject {
  async load(): Promise<Session> {
    return (await this.ctx.storage.get<Session>(STATE_KEY)) ?? emptySession();
  }

  /** Thêm một lượt, tính từ trạng thái đang lưu trong chính DO (không ghi đè lệch giữa các request). */
  async record(question: string, answer: string, eventIds: string[]): Promise<void> {
    const current = await this.load();
    await this.ctx.storage.put(STATE_KEY, nextSession(current, question, answer, eventIds));
    await this.ctx.storage.setAlarm(Date.now() + SESSION_TTL_MS); // gia hạn TTL mỗi lượt
  }

  /** Hết 30 phút không hoạt động: xoá phiên. */
  async alarm(): Promise<void> {
    await this.ctx.storage.deleteAll();
  }
}
