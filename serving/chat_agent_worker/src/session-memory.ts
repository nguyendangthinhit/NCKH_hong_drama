// Bộ nhớ phiên: sự kiện gần nhất và vài lượt hội thoại của từng người dùng. Port của session_memory.py.
// Phần thuần (kiểu + cách tính phiên mới) ở đây để test được trong Node;
// lưu trữ nhất quán nằm ở Durable Object (session-durable-object.ts).
import { Turn } from "./answer-prompt";

export const MAX_TURNS = 3; // số lượt (hỏi + đáp) giữ lại để LLM hiểu ngữ cảnh
export const SESSION_TTL_MS = 30 * 60 * 1000; // phiên không hoạt động 30 phút thì xoá

export interface Session {
  lastEventIds: string[];
  turns: Turn[];
}

export const emptySession = (): Session => ({ lastEventIds: [], turns: [] });

/** Phiên sau khi thêm một lượt; lượt không khớp sự kiện thì giữ sự kiện đang bàn. */
export function nextSession(
  session: Session, question: string, answer: string, eventIds: string[],
): Session {
  return {
    lastEventIds: eventIds.length ? eventIds : session.lastEventIds,
    turns: [...session.turns, [question, answer] as Turn].slice(-MAX_TURNS),
  };
}

/** Kiểm tra dạng dữ liệu đọc từ lưu trữ (phòng dữ liệu cũ/hỏng). */
export const isSession = (v: unknown): boolean =>
  !!v && Array.isArray((v as Session).lastEventIds) && Array.isArray((v as Session).turns);
