// Luồng xử lý một tin nhắn: luật -> khớp sự kiện/insight -> đúng 1 lần LLM. Port của chat_pipeline.py.
import { buildUserPrompt, SYSTEM_PROMPT } from "./answer-prompt";
import { EVENT_BY_ID, matchEvents } from "./event-store";
import { eventText, statsText, topEventsText } from "./insight-context";
import * as rules from "./intent-rules";
import { LLMUnavailable } from "./llm-client";
import { Session } from "./session-memory";

// Câu hỏi top/thống kê mà vẫn khớp mạnh một sự kiện thì trả lời theo sự kiện thay vì số liệu toàn hệ thống.
const STRONG_EVENT_SCORE = 20.0;
const LLM_DOWN_REPLY = "Hệ thống đang bận, bạn thử hỏi lại sau ít phút nhé.";

export type LlmFn = (system: string, user: string) => Promise<{ text: string; provider: string }>;

export interface ChatResult {
  reply: string;
  intent: string;
  event_ids: string[];
  timings_ms: Record<string, number>;
  provider: string;
}

const fixed = (reply: string, intent: string, timings: Record<string, number> = {}): ChatResult =>
  ({ reply, intent, event_ids: [], timings_ms: timings, provider: "" });

export async function handleMessage(session: Session, rawMessage: string, llm: LlmFn): Promise<ChatResult> {
  const t0 = Date.now();
  const result = await route(session, rawMessage.trim(), llm);
  result.timings_ms.total = Date.now() - t0;
  return result;
}

async function route(session: Session, message: string, llm: LlmFn): Promise<ChatResult> {
  if (rules.isSpam(message)) return fixed(rules.SPAM_REPLY, "spam");
  if (rules.isGreetingOnly(message)) return fixed(rules.GREETING_REPLY, "greeting");
  if (rules.isInfo(message)) return fixed(rules.INFO_REPLY, "info");

  const match = matchEvents(message);
  const category = rules.categoryHint(message);
  const wantsTop = rules.isTopRequest(message);
  const wantsStats = rules.isStatsRequest(message);
  const weakEvent = match.score < STRONG_EVENT_SCORE;

  if ((wantsTop || wantsStats) && (!match.events.length || weakEvent)) {
    const context = wantsTop ? topEventsText(category) : statsText(category);
    return answer(session, message, context, wantsTop ? "insights_top" : "insights_stats", [], llm);
  }

  let events = match.events;
  let intent = "event";
  // Câu hỏi nối tiếp ("vụ đó", "dư luận thế nào"): ưu tiên sự kiện đang bàn trong phiên,
  // trừ khi câu hỏi khớp mạnh một sự kiện khác.
  const previous = session.lastEventIds.flatMap((id) => EVENT_BY_ID.get(id) ?? []);
  const refersBack = rules.isFollowup(message) && (!events.length || weakEvent);
  const opinionOnly = !events.length && rules.isOpinionRequest(message);
  if (previous.length && (refersBack || opinionOnly)) {
    events = previous;
    intent = "event_followup";
  }
  if (events.length) {
    const withStats = rules.isOpinionRequest(message) || wantsStats;
    const context = events.map((e) => eventText(e, withStats)).join("\n\n---\n\n");
    return answer(session, message, context, intent, events.map((e) => e.id), llm);
  }
  return rules.mentionsDrama(message)
    ? fixed(rules.CLARIFY_REPLY, "clarify")
    : fixed(rules.UNRELATED_REPLY, "unrelated");
}

async function answer(
  session: Session, question: string, context: string, intent: string, eventIds: string[], llm: LlmFn,
): Promise<ChatResult> {
  const prompt = buildUserPrompt(question, context, session.turns);
  const t = Date.now();
  let reply = LLM_DOWN_REPLY;
  let provider = "";
  try {
    ({ text: reply, provider } = await llm(SYSTEM_PROMPT, prompt));
  } catch (e) {
    if (!(e instanceof LLMUnavailable)) throw e;
    console.error("LLM không khả dụng:", e.message);
  }
  return { reply, intent, event_ids: eventIds, timings_ms: { llm: Date.now() - t }, provider };
}
