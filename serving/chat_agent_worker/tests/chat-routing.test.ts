// Port của tests/test_chat_routing.py: luật ý định, khớp sự kiện trên dữ liệu thật, định tuyến pipeline (LLM giả).
import { describe, expect, it } from "vitest";
import { handleMessage, LlmFn } from "../src/chat-pipeline";
import { matchEvents } from "../src/event-store";
import * as rules from "../src/intent-rules";
import { LLMUnavailable } from "../src/llm-client";
import { emptySession, isSession, MAX_TURNS, nextSession, Session } from "../src/session-memory";

const llmDown: LlmFn = async () => {
  throw new LLMUnavailable("test");
};
const llmEcho: LlmFn = async () => ({ text: "ok", provider: "test" });

describe("luật ý định", () => {
  it("nhận diện đúng", () => {
    expect(rules.isGreetingOnly("hello")).toBe(true);
    expect(rules.isGreetingOnly("Xin chào bạn")).toBe(true);
    expect(rules.isGreetingOnly("hello, vụ Jack là gì")).toBe(false);
    expect(rules.isInfo("bạn là ai vậy")).toBe(true);
    expect(rules.isSpam("đm bot")).toBe(true);
    expect(rules.isSpam("trường lớn nhất")).toBe(false); // "lớn" không phải từ tục
    expect(rules.isSpam("")).toBe(true);
    expect(rules.isTopRequest("Top những drama được quan tâm nhất")).toBe(true);
    expect(rules.categoryHint("top drama giáo dục")).toBe("education");
  });
});

describe("khớp sự kiện", () => {
  it.each([
    ["Vụ việc học sinh Hưng Yên đạo nhái thi KHKT", "education", "đạo nhái"],
    ["Công ty của Shark Thủy nợ lương giáo viên như thế nào?", "education", "Shark Thuỷ"],
    ["cô giáo 231 cái tát", "education", "231"],
    ["Mailisa", "showbiz", "Mailisa"],
    ["Tizi và Đích Lép bị đồn đoán chuyện gì về hôn nhân?", "showbiz", "Tizi"],
  ])("%s", (question, prefix, word) => {
    const m = matchEvents(question);
    expect(m.events.length).toBeGreaterThan(0);
    expect(m.events[0].id.startsWith(prefix)).toBe(true);
    expect(m.events[0].title.toLowerCase()).toContain(word.toLowerCase());
  });

  it("người có nhiều vụ trả về nhóm", () => {
    const m = matchEvents("Thông tin về drama của Viruss");
    expect(m.events.length).toBeGreaterThanOrEqual(2);
    expect(m.events.slice(0, 2).every((e) => e.title.toLowerCase().includes("viruss"))).toBe(true);
  });

  it.each(["sự kiện của miu lê", "giá vàng hôm nay", "Xin chào"])("không khớp nhầm: %s", (q) => {
    expect(matchEvents(q).events).toEqual([]);
  });
});

describe("pipeline", () => {
  const fresh = (): Session => emptySession();

  it("câu trả lời cố định", async () => {
    expect((await handleMessage(fresh(), "hello", llmDown)).intent).toBe("greeting");
    expect((await handleMessage(fresh(), "bạn làm được gì", llmDown)).intent).toBe("info");
    expect((await handleMessage(fresh(), "giá vàng hôm nay", llmDown)).intent).toBe("unrelated");
    expect((await handleMessage(fresh(), "drama của miu lê", llmDown)).intent).toBe("clarify");
  });

  it("insights và câu hỏi nối tiếp", async () => {
    const s = fresh();
    expect((await handleMessage(s, "Top những drama được quan tâm nhất", llmEcho)).intent).toBe("insights_top");
    expect((await handleMessage(s, "có drama giáo dục nào không", llmEcho)).intent).toBe("insights_top");
    const first = await handleMessage(s, "Vì sao Trường Quốc tế Mỹ bị giải thể?", llmEcho);
    expect(first.intent).toBe("event");
    expect(first.event_ids.length).toBeGreaterThan(0);
    const s2 = nextSession(s, "q", first.reply, first.event_ids); // index.ts ghi qua Durable Object
    const follow = await handleMessage(s2, "dư luận phản ứng thế nào về vụ đó", llmEcho);
    expect(follow.intent).toBe("event_followup");
    expect(follow.event_ids).toEqual(first.event_ids);
  });

  it("LLM sập thì trả câu báo bận, không ném lỗi", async () => {
    const r = await handleMessage(fresh(), "Mailisa", llmDown);
    expect(r.intent).toBe("event");
    expect(r.reply).toContain("bận");
  });
});

describe("nextSession", () => {
  it("giữ sự kiện cũ khi lượt mới không khớp, cắt còn MAX_TURNS lượt", () => {
    let s = nextSession(emptySession(), "q1", "a1", ["showbiz_034"]);
    s = nextSession(s, "q2", "a2", []);
    expect(s.lastEventIds).toEqual(["showbiz_034"]);
    for (let i = 3; i <= 6; i++) s = nextSession(s, `q${i}`, `a${i}`, []);
    expect(s.turns.length).toBe(MAX_TURNS);
    expect(s.turns.at(-1)).toEqual(["q6", "a6"]);
    expect(nextSession(s, "q7", "a7", ["education_001"]).lastEventIds).toEqual(["education_001"]);
    expect(isSession(s)).toBe(true);
    expect(isSession(null)).toBe(false);
    expect(isSession({ turns: [] })).toBe(false);
  });
});
