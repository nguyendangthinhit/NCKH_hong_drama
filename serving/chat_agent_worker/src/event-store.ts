// Kho sự kiện + so khớp câu hỏi (điểm từ vựng trọng số IDF) trên chỉ mục dựng sẵn. Port của event_store.py.
import data from "./generated/agent-data.json";
import { terms } from "./text-normalizer";

export interface Actor { name?: string; role?: string; [k: string]: unknown }
export interface AgentEvent {
  id: string;
  category: "showbiz" | "education";
  title: string;
  content: string;
  actors: Actor[];
  time_event: string;
  analyzed: Record<string, unknown>;
}
/** term -> [idf, chỉ số sự kiện trúng tiêu đề/nhân vật, chỉ số sự kiện chỉ trúng thân bài] */
type TermIndex = Record<string, [number, number[], number[]]>;

export const EVENTS = data.events as unknown as AgentEvent[];
export const EVENT_BY_ID = new Map(EVENTS.map((e) => [e.id, e]));
export const INSIGHTS = data.insights as Record<string, any>;
const INDEX = data.terms as unknown as TermIndex;

// Trọng số: khớp ở tiêu đề / tên nhân vật đáng tin hơn khớp trong thân bài.
const TITLE_WEIGHT = 3.0;
const CONTENT_WEIGHT = 1.0;
// Ngưỡng chọn sự kiện (hiệu chỉnh trên câu hỏi thật, 2026-11-05).
const MIN_SCORE = 6.0;
const BODY_ONLY_MIN = 15.0;
const GROUP_RATIO = 0.75;
const MAX_EVENTS = 3;

export interface MatchResult {
  events: AgentEvent[]; // rỗng nếu không khớp; phần tử đầu là khớp nhất
  score: number;
  runnerUp: number;
}

export function matchEvents(question: string): MatchResult {
  const scores = new Array<number>(EVENTS.length).fill(0);
  const headHit = new Array<boolean>(EVENTS.length).fill(false);
  for (const t of terms(question)) {
    const entry = INDEX[t];
    if (!entry) continue;
    const [idf, head, body] = entry;
    for (const i of head) {
      scores[i] += TITLE_WEIGHT * idf;
      headHit[i] = true;
    }
    for (const i of body) scores[i] += CONTENT_WEIGHT * idf;
  }
  // Array.sort ổn định: điểm bằng nhau giữ thứ tự gốc, như Python.
  const order = scores.map((_, i) => i).sort((a, b) => scores[b] - scores[a]);
  if (!order.length) return { events: [], score: 0, runnerUp: 0 };
  const top = scores[order[0]];
  const runnerUp = order.length > 1 ? scores[order[1]] : 0;
  if (top < MIN_SCORE || (!headHit[order[0]] && top < BODY_ONLY_MIN)) {
    return { events: [], score: top, runnerUp };
  }
  const group = order
    .slice(0, MAX_EVENTS)
    .filter((i) => scores[i] >= GROUP_RATIO * top)
    .map((i) => EVENTS[i]);
  return { events: group, score: top, runnerUp };
}
