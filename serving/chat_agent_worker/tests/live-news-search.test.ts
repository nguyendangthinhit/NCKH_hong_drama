// Tra tin web (Firecrawl) trong pipeline: dùng tool giả để không tốn credit; kiểm định tuyến, ngữ cảnh, nguồn.
import { describe, expect, it } from "vitest";
import { handleMessage, LlmFn } from "../src/chat-pipeline";
import { matchEvents } from "../src/event-store";
import * as rules from "../src/intent-rules";
import { cleanArticleMarkdown, NewsFn, NewsItem, searchLatestNews } from "../src/live-news-search";
import { buildSearchQuery, eventSearchQuery, isSubjectlessLatestRequest, searchKeywords } from "../src/news-search-query";
import { emptySession, nextSession } from "../src/session-memory";
import type { Env } from "../src/env";

const ITEM: NewsItem = {
  title: "Ca sĩ X bị chỉ trích vì phát ngôn", url: "https://kenh14.vn/bai-1", source: "kenh14.vn",
  date: "2 days ago", content: "Nội dung bài báo về phát ngôn của ca sĩ X gây tranh cãi trên mạng xã hội.",
};

/** Tool giả: ghi lại các lần gọi, trả danh sách cho trước. */
function fakeNews(items: NewsItem[]) {
  const calls: { query: string; recent: boolean }[] = [];
  const fn: NewsFn = async (query, recent) => {
    calls.push({ query, recent });
    return items;
  };
  return { fn, calls };
}

/** LLM giả: lưu prompt để kiểm ngữ cảnh đưa vào. */
function captureLlm() {
  const prompts: string[] = [];
  const fn: LlmFn = async (_sys, user) => {
    prompts.push(user);
    return { text: "trả lời", provider: "test" };
  };
  return { fn, prompts };
}

describe("luật tin mới", () => {
  it("nhận diện câu hỏi mới nhất", () => {
    expect(rules.isLatestRequest("Shark Bình mới nhất ra sao")).toBe(true);
    expect(rules.isLatestRequest("drama showbiz gần đây")).toBe(true);
    expect(rules.isLatestRequest("vụ đó có gì mới không")).toBe(true);
    expect(rules.isLatestRequest("giáo dục có drama gì mới không")).toBe(true);
    expect(rules.isLatestRequest("Mailisa")).toBe(false);
  });
});

describe("pipeline + tra tin web", () => {
  it("không có trong kho local -> tra web thay vì trả 'chưa có', có nguồn", async () => {
    const news = fakeNews([ITEM]);
    const llm = captureLlm();
    const r = await handleMessage(emptySession(), "drama của miu lê", llm.fn, news.fn);
    expect(r.intent).toBe("live_news");
    expect(news.calls).toEqual([{ query: "miu lê", recent: false }]);
    expect(llm.prompts[0]).toContain("TIN MỚI TỪ WEB");
    expect(llm.prompts[0]).toContain(ITEM.content);
    expect(r.reply).toContain("Nguồn tin:\nhttps://kenh14.vn/bai-1");
    expect(r.timings_ms.web).toBeGreaterThanOrEqual(0);
  });

  it("web không có kết quả -> giữ câu hỏi lại như cũ", async () => {
    const r = await handleMessage(emptySession(), "drama của miu lê", captureLlm().fn, fakeNews([]).fn);
    expect(r.intent).toBe("clarify");
  });

  it("ngoài phạm vi drama thì không tra web", async () => {
    const news = fakeNews([ITEM]);
    const r = await handleMessage(emptySession(), "giá vàng hôm nay", captureLlm().fn, news.fn);
    expect(r.intent).toBe("unrelated");
    expect(news.calls.length).toBe(0);
  });

  it("sự kiện có sẵn + hỏi mới nhất -> ghép dữ liệu local và tin web, tìm theo tên sự kiện", async () => {
    const news = fakeNews([ITEM]);
    const llm = captureLlm();
    const r = await handleMessage(emptySession(), "Mailisa có tin gì mới nhất", llm.fn, news.fn);
    const ev = matchEvents("Mailisa").events[0];
    expect(r.intent).toBe("event_live");
    expect(r.event_ids[0]).toBe(ev.id);
    expect(news.calls[0]).toEqual({ query: "Mailisa", recent: true });
    expect(llm.prompts[0]).toContain(ev.title);
    expect(llm.prompts[0]).toContain("TIN MỚI TỪ WEB");
  });

  it("sự kiện có sẵn, không hỏi mới nhất -> không tốn credit", async () => {
    const news = fakeNews([ITEM]);
    expect((await handleMessage(emptySession(), "Mailisa", captureLlm().fn, news.fn)).intent).toBe("event");
    expect(news.calls.length).toBe(0);
  });

  it("'drama nào hot gần đây' -> tin web; web rỗng -> top từ kho local", async () => {
    const q = "drama nào đang hot gần đây";
    expect((await handleMessage(emptySession(), q, captureLlm().fn, fakeNews([ITEM]).fn)).intent).toBe("live_news");
    expect((await handleMessage(emptySession(), q, captureLlm().fn, fakeNews([]).fn)).intent).toBe("insights_top");
  });

  it("hỏi nối tiếp 'có gì mới không' -> tra theo sự kiện đang bàn", async () => {
    const first = await handleMessage(emptySession(), "Mailisa", captureLlm().fn);
    const s = nextSession(emptySession(), "Mailisa", first.reply, first.event_ids);
    const news = fakeNews([ITEM]);
    const r = await handleMessage(s, "có gì mới không", captureLlm().fn, news.fn);
    expect(r.intent).toBe("event_followup_live");
    expect(r.event_ids).toEqual(first.event_ids);
    expect(news.calls.length).toBe(1);
  });
});

describe("tool Firecrawl", () => {
  it("thiếu khoá -> trả rỗng, không gọi mạng", async () => {
    expect(await searchLatestNews({} as Env, "abc", true)).toEqual([]);
  });

  it("làm sạch markdown bài báo", () => {
    const md = [
      "[Bỏ qua đến nội dung chính](https://x.vn#content)",
      "- [Video](https://x.vn/video)",
      "![ảnh](https://x.vn/a.jpg)",
      "# Shark Bình lãnh 10 năm tù vì rửa tiền gần 320 tỉ đồng trong vụ án Mr Pips",
      "Trong vụ án Mr Pips, **Shark Bình** bị cáo buộc giúp [Mr Pips](https://x.vn/p) rửa tiền qua ví điện tử.",
      "Trong vụ án Mr Pips, **Shark Bình** bị cáo buộc giúp [Mr Pips](https://x.vn/p) rửa tiền qua ví điện tử.",
    ].join("\n");
    const out = cleanArticleMarkdown(md);
    expect(out).not.toContain("http");
    expect(out).not.toContain("Video");
    expect(out.split("\n")).toEqual([
      "Shark Bình lãnh 10 năm tù vì rửa tiền gần 320 tỉ đồng trong vụ án Mr Pips",
      "Trong vụ án Mr Pips, Shark Bình bị cáo buộc giúp Mr Pips rửa tiền qua ví điện tử.",
    ]);
  });
});

describe("dựng câu tìm tin", () => {
  it.each([
    ["Shark Bình có tin gì mới nhất", "Shark Bình"],
    ["drama của Miu Lê", "Miu Lê"],
    ["Hiền Hồ dạo này thế nào rồi?", "Hiền Hồ"],
    ["cô giáo bị tố đánh học sinh gần đây", "cô giáo tố đánh học sinh"],
    ["Nhật Kim Anh có ồn ào gì không", "Nhật Kim Anh"],
  ])("từ khoá: %s", (q, kw) => {
    expect(searchKeywords(q)).toBe(kw);
  });

  it("chỉ còn tên lĩnh vực -> câu tìm chung", () => {
    expect(buildSearchQuery("drama showbiz nào đang hot gần đây")).toBe("ồn ào showbiz Việt");
    expect(buildSearchQuery("giáo dục có drama gì mới không")).toBe("giáo dục gây xôn xao");
    expect(buildSearchQuery("có drama gì mới nhất không")).toBe("ồn ào showbiz Việt");
    expect(buildSearchQuery("drama của Miu Lê")).toBe("Miu Lê");
  });

  it("chủ thể sự kiện từ tiêu đề", () => {
    const jack = "Jack (J97) – tranh chấp với Thiên An liên quan việc công khai con chung";
    expect(eventSearchQuery(jack)).toBe("Jack J97");
    expect(eventSearchQuery("Shark Bình từ 'cá mập' đến tội phạm lừa đảo, rửa tiền")).toBe("Shark Bình từ cá mập đến");
    expect(eventSearchQuery("x – y", "Shark Bình có tin gì mới nhất")).toBe("Shark Bình");
    expect(eventSearchQuery(jack, "vụ đó có gì mới không")).toBe("Jack J97");
  });
});

describe("định tuyến tin mới: hồi quy từ lần chạy thật", () => {
  it.each([
    "Có diễn biến gì mới nữa không?",
    "Có diễn biến nào mới không?",
    "Có thêm diễn biến nào mới không?",
    "Có thông tin gì mới nữa không?",
    "Vậy có diễn biến gì mới nữa không?",
    "Co dien bien gi moi nua khong?",
  ])("hỏi tiếp sau kẹo Kera giữ đúng sự kiện: %s", async (question) => {
    const news = fakeNews([ITEM]);
    const llm = captureLlm();
    const first = await handleMessage(emptySession(), "Vụ kẹo Kera có tin gì mới nhất?", llm.fn, news.fn);
    expect(first.intent).toBe("event_live");
    expect(first.event_ids).toEqual(["showbiz_019"]);
    const session = nextSession(emptySession(), "Vụ kẹo Kera có tin gì mới nhất?", first.reply, first.event_ids);
    const reply = await handleMessage(session, question, llm.fn, news.fn);
    expect(reply.intent).toBe("event_followup_live");
    expect(reply.event_ids).toEqual(first.event_ids);
    expect(news.calls.at(-1)).toEqual({ query: "Scandal kẹo Kera", recent: true });
    expect(news.calls).toHaveLength(2);
    expect(llm.prompts.at(-1)).toContain("Kera");
  });

  it("web rỗng vẫn giữ ngữ cảnh Kera khi hỏi tiếp", async () => {
    const news = fakeNews([]);
    const llm = captureLlm();
    const first = await handleMessage(emptySession(), "Vụ kẹo Kera có tin gì mới nhất?", llm.fn, news.fn);
    const session = nextSession(emptySession(), "Vụ kẹo Kera có tin gì mới nhất?", first.reply, first.event_ids);
    const reply = await handleMessage(session, "Có diễn biến gì mới nữa không?", llm.fn, news.fn);
    expect(reply.intent).toBe("event_followup");
    expect(reply.event_ids).toEqual(["showbiz_019"]);
    expect(news.calls.at(-1)).toEqual({ query: "Scandal kẹo Kera", recent: true });
  });

  it("phiên mới chưa biết sự kiện thì hỏi lại thay vì mượn ngữ cảnh", async () => {
    const news = fakeNews([ITEM]);
    const llm = captureLlm();
    const reply = await handleMessage(emptySession(), "Có diễn biến gì mới nữa không?", llm.fn, news.fn);
    expect(reply.intent).toBe("clarify");
    expect(reply.event_ids).toEqual([]);
    expect(news.calls).toHaveLength(0);
    expect(llm.prompts).toHaveLength(0);
  });

  it.each([
    "Giá vàng hôm nay",
    "Điện Biên có gì mới không?",
  ])("chủ thể ngoài phạm vi không bị kéo về Kera: %s", async (question) => {
    const first = await handleMessage(emptySession(), "Vụ kẹo Kera", captureLlm().fn);
    const session = nextSession(emptySession(), "Vụ kẹo Kera", first.reply, first.event_ids);
    const news = fakeNews([ITEM]);
    const reply = await handleMessage(session, question, captureLlm().fn, news.fn);
    expect(reply.intent).toBe("unrelated");
    expect(reply.event_ids).toEqual([]);
    expect(news.calls).toHaveLength(0);
  });

  it("nêu sự kiện mới thì chuyển từ Kera sang sự kiện mới", async () => {
    const first = await handleMessage(emptySession(), "Vụ kẹo Kera", captureLlm().fn);
    const session = nextSession(emptySession(), "Vụ kẹo Kera", first.reply, first.event_ids);
    const news = fakeNews([ITEM]);
    const reply = await handleMessage(session, "Mailisa có tin gì mới nhất?", captureLlm().fn, news.fn);
    expect(reply.intent).toBe("event_live");
    expect(reply.event_ids).toEqual(["showbiz_020"]);
    expect(news.calls.at(-1)).toEqual({ query: "Mailisa", recent: true });
  });

  it.each([
    "Giá vàng hôm nay có diễn biến gì mới không?",
    "Điện Biên có gì mới không?",
    "Mailisa có diễn biến gì mới không?",
    "Hiền Hồ có thông tin gì mới không?",
  ])("bộ nhận diện câu hỏi không chủ thể giữ nguyên tên riêng: %s", (question) => {
    expect(isSubjectlessLatestRequest(question)).toBe(false);
  });

  it("'giá vàng hôm nay' sau một sự kiện trong phiên vẫn là ngoài phạm vi", async () => {
    const first = await handleMessage(emptySession(), "Mailisa", captureLlm().fn);
    const s = nextSession(emptySession(), "Mailisa", first.reply, first.event_ids);
    const news = fakeNews([ITEM]);
    expect((await handleMessage(s, "giá vàng hôm nay", captureLlm().fn, news.fn)).intent).toBe("unrelated");
    expect(news.calls.length).toBe(0);
  });

  it("'drama giáo dục gần đây' -> tin web chung, không kể sự kiện cũ khớp yếu", async () => {
    const news = fakeNews([ITEM]);
    const r = await handleMessage(emptySession(), "drama giáo dục gần đây", captureLlm().fn, news.fn);
    expect(r.intent).toBe("live_news");
    expect(news.calls).toEqual([{ query: "giáo dục gây xôn xao", recent: true }]);
  });

  it("web rỗng thì không gọi lại lần hai", async () => {
    const news = fakeNews([]);
    await handleMessage(emptySession(), "drama mới nhất", captureLlm().fn, news.fn);
    expect(news.calls.length).toBe(1);
  });
});
