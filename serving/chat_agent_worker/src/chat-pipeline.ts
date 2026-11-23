// Luồng xử lý một tin nhắn: luật -> khớp sự kiện/insight (+ tra tin web khi cần) -> đúng 1 lần LLM.
// Port của chat_pipeline.py.
import { buildUserPrompt, SYSTEM_PROMPT } from "./answer-prompt";
import { EVENT_BY_ID, matchEvents } from "./event-store";
import { eventText, statsText, topEventsText } from "./insight-context";
import * as rules from "./intent-rules";
import { newsContextText, NewsFn, NewsItem, sourcesText } from "./live-news-search";
import { buildSearchQuery, eventSearchQuery, isGenericQuestion, isSubjectlessLatestRequest, searchKeywords } from "./news-search-query";
import { LLMUnavailable } from "./llm-client";
import { Session } from "./session-memory";

// Câu hỏi top/thống kê mà vẫn khớp mạnh một sự kiện thì trả lời theo sự kiện thay vì số liệu toàn hệ thống.
const STRONG_EVENT_SCORE = 20.0;
const LLM_DOWN_REPLY = "Hệ thống đang bận, bạn thử hỏi lại sau ít phút nhé.";
const noNews: NewsFn = async () => [];

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

export async function handleMessage(
  session: Session, rawMessage: string, llm: LlmFn, news: NewsFn = noNews,
): Promise<ChatResult> {
  const t0 = Date.now();
  const result = await route(session, rawMessage.trim(), llm, timedNews(news));
  result.timings_ms.total = Date.now() - t0;
  return result;
}

/** Bọc tool tìm tin để ghi thời gian vào timings_ms.web. */
function timedNews(news: NewsFn) {
  return async (timings: Record<string, number>, query: string, recent: boolean): Promise<NewsItem[]> => {
    const t = Date.now();
    const items = await news(query, recent);
    timings.web = Date.now() - t;
    return items;
  };
}

async function route(
  session: Session, message: string, llm: LlmFn, news: ReturnType<typeof timedNews>,
): Promise<ChatResult> {
  if (rules.isSpam(message)) return fixed(rules.SPAM_REPLY, "spam");
  if (rules.isGreetingOnly(message)) return fixed(rules.GREETING_REPLY, "greeting");
  if (rules.isInfo(message)) return fixed(rules.INFO_REPLY, "info");

  const match = matchEvents(message);
  const category = rules.categoryHint(message);
  const wantsTop = rules.isTopRequest(message);
  const wantsStats = rules.isStatsRequest(message);
  const subjectlessLatest = isSubjectlessLatestRequest(message);
  const wantsLatest = rules.isLatestRequest(message) || subjectlessLatest;
  const weakEvent = match.score < STRONG_EVENT_SCORE;
  const noStrongEvent = !match.events.length || weakEvent;
  const inScope = rules.mentionsDrama(message) || category !== null;
  const timings: Record<string, number> = {};
  let webTried = false;

  // Hỏi tin mới chung chung ("drama nào hot gần đây", "drama giáo dục gần đây"): kho local là số liệu cũ
  // và chỉ khớp yếu -> ưu tiên tin web; web rỗng thì đi tiếp luồng cũ.
  if (wantsLatest && noStrongEvent && (wantsTop || (inScope && isGenericQuestion(message)))) {
    webTried = true;
    const items = await news(timings, buildSearchQuery(message), true);
    if (items.length) return answer(session, message, newsContextText(items), "live_news", [], llm, timings, items);
  }

  if ((wantsTop || wantsStats) && noStrongEvent) {
    const context = wantsTop ? topEventsText(category) : statsText(category);
    return answer(session, message, context, wantsTop ? "insights_top" : "insights_stats", [], llm, timings);
  }

  let events = match.events;
  let intent = "event";
  // Câu hỏi nối tiếp ("vụ đó", "dư luận thế nào"): ưu tiên sự kiện đang bàn trong phiên,
  // trừ khi câu hỏi khớp mạnh một sự kiện khác.
  const previous = session.lastEventIds.flatMap((id) => EVENT_BY_ID.get(id) ?? []);
  if (subjectlessLatest && !previous.length) return fixed(rules.CLARIFY_REPLY, "clarify", timings);
  const refersBack = rules.isFollowup(message) && (!events.length || weakEvent);
  const opinionOnly = !events.length && rules.isOpinionRequest(message);
  // "có gì mới không": hỏi tin mới mà không nêu chủ thể nào -> về sự kiện đang bàn.
  // ("giá vàng hôm nay" có từ khoá riêng nên không bị kéo về sự kiện cũ.)
  const latestFollowup = subjectlessLatest || (wantsLatest && !events.length && !inScope && !searchKeywords(message));
  if (previous.length && (refersBack || opinionOnly || latestFollowup)) {
    events = previous;
    intent = "event_followup";
  }
  if (events.length) {
    const ids = events.map((e) => e.id);
    const withStats = rules.isOpinionRequest(message) || wantsStats;
    let context = events.map((e) => eventText(e, withStats)).join("\n\n---\n\n");
    // Hỏi diễn biến mới của sự kiện đã có: ghép thêm tin web (tìm theo chủ thể của sự kiện đầu tiên).
    if (wantsLatest) {
      const items = await news(timings, eventSearchQuery(events[0].title, intent === "event" ? message : undefined), true);
      if (items.length) {
        context += `\n\n---\n\n${newsContextText(items)}`;
        return answer(session, message, context, `${intent}_live`, ids, llm, timings, items);
      }
    }
    return answer(session, message, context, intent, ids, llm, timings);
  }
  // Kho local không có: thay vì trả "chưa có", tra tin trên web nếu câu hỏi thuộc phạm vi drama.
  if (inScope) {
    const items = webTried ? [] : await news(timings, buildSearchQuery(message), wantsLatest);
    if (items.length) return answer(session, message, newsContextText(items), "live_news", [], llm, timings, items);
    return fixed(rules.CLARIFY_REPLY, "clarify", timings);
  }
  return fixed(rules.UNRELATED_REPLY, "unrelated", timings);
}

async function answer(
  session: Session, question: string, context: string, intent: string, eventIds: string[],
  llm: LlmFn, timings: Record<string, number>, webItems: NewsItem[] = [],
): Promise<ChatResult> {
  const prompt = buildUserPrompt(question, context, session.turns);
  const t = Date.now();
  let reply = LLM_DOWN_REPLY;
  let provider = "";
  try {
    ({ text: reply, provider } = await llm(SYSTEM_PROMPT, prompt));
    reply += sourcesText(webItems);
  } catch (e) {
    if (!(e instanceof LLMUnavailable)) throw e;
    console.error("LLM không khả dụng:", e.message);
  }
  return { reply, intent, event_ids: eventIds, timings_ms: { ...timings, llm: Date.now() - t }, provider };
}
