// Tra tin web (Firecrawl) trong pipeline: dùng tool giả để không tốn credit; kiểm định tuyến, ngữ cảnh, nguồn.
import { describe, expect, it } from "vitest";
import { handleMessage, LlmFn } from "../src/chat-pipeline";
import { matchEvents } from "../src/event-store";
import * as rules from "../src/intent-rules";
import { cleanArticleMarkdown, NewsFn, NewsItem, searchLatestNews } from "../src/live-news-search";
import { buildSearchQuery, eventSearchQuery, searchKeywords } from "../src/news-search-query";
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
