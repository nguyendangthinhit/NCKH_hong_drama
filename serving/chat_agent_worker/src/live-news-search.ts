// Tool tra tin mới trên web qua Firecrawl: tìm tin báo (/v2/search, nguồn news, Việt Nam), rồi scrape
// song song vài bài đầu để lấy nội dung. Dùng khi kho sự kiện local không có / cần cập nhật mới nhất.
// Port sang Python: serving/chat_agent/live_news_search.py (giữ cùng hành vi).
import { Env } from "./env";

const API = "https://api.firecrawl.dev/v2";
const SEARCH_TIMEOUT_MS = 10_000;
const SCRAPE_TIMEOUT_MS = 12_000;
const SEARCH_LIMIT = 5;
const ARTICLE_CHARS = 1500;
const CACHE_TTL_S = 30 * 60; // cùng câu tìm trong 30 phút dùng lại kết quả (tiết kiệm credit)

export interface NewsItem {
  title: string;
  url: string;
  source: string; // tên miền báo
  date: string; // thời điểm tương đối do Google News trả (vd "4 days ago")
  content: string; // đoạn nội dung đã làm sạch, rỗng nếu không scrape được
}

/** recent = chỉ lấy tin trong 1 tuần; ngược lại trong 1 năm. */
export type NewsFn = (query: string, recent: boolean) => Promise<NewsItem[]>;

const hostOf = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
};

/** Markdown bài báo -> đoạn văn bản thuần: bỏ ảnh/link/menu (dòng ngắn), giữ các đoạn văn đầu. */
export function cleanArticleMarkdown(md: string, maxChars = ARTICLE_CHARS): string {
  const lines = md
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "") // ảnh
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1") // link -> chữ
    .split("\n")
    .map((l) => l.replace(/^[#>*\-\s|]+/, "").replace(/[*_`|]+/g, "").trim())
    .filter((l) => l.length >= 60); // dòng menu, nút, chú thích ảnh thường ngắn
  const out: string[] = [];
  let size = 0;
  for (const l of lines) {
    if (out.includes(l)) continue;
    out.push(l);
    size += l.length;
    if (size >= maxChars) break;
  }
  return out.join("\n").slice(0, maxChars);
}

/** Văn bản đưa vào phần DỮ LIỆU của prompt. */
export function newsContextText(items: NewsItem[], today = new Date()): string {
  const day = today.toISOString().slice(0, 10);
  const blocks = items.map((it, i) => {
    const head = `[${i + 1}] ${it.title} | Báo: ${it.source} | Thời gian: ${it.date || "không rõ"}`;
    return it.content ? `${head}\nNội dung: ${it.content}` : head;
  });
  return `TIN MỚI TỪ WEB (tìm ngày ${day}, chưa qua phân tích dư luận của hệ thống):\n${blocks.join("\n\n")}`;
}

/** Danh sách link nguồn nối vào cuối câu trả lời. */
export const sourcesText = (items: NewsItem[], max = 3): string =>
  items.length ? `\n\nNguồn tin:\n${items.slice(0, max).map((it) => it.url).join("\n")}` : "";

async function post(env: Env, path: string, body: unknown, timeoutMs: number): Promise<any> {
  const resp = await fetch(`${API}/${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.FIRECRAWL_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!resp.ok) throw new Error(`Firecrawl ${path} HTTP ${resp.status}`);
  return resp.json();
}

async function scrapeContent(env: Env, url: string): Promise<string> {
  try {
    const json = await post(env, "scrape",
      { url, formats: ["markdown"], onlyMainContent: true, timeout: SCRAPE_TIMEOUT_MS - 2000 },
      SCRAPE_TIMEOUT_MS);
    return cleanArticleMarkdown(json?.data?.markdown ?? "");
  } catch (e) {
    console.warn(`Scrape lỗi ${hostOf(url)}: ${(e as Error).message}`);
    return ""; // vẫn dùng được tiêu đề
  }
}

/** Tìm tin; lỗi/không có khoá thì trả [] để pipeline quay về câu trả lời cũ. */
export async function searchLatestNews(env: Env, query: string, recent: boolean): Promise<NewsItem[]> {
  if (!env.FIRECRAWL_API_KEY) return [];
  const q = query.trim().slice(0, 200);
  const tbs = recent ? "qdr:w" : "qdr:y";
  const cache = typeof caches !== "undefined" ? caches.default : null;
  const cacheKey = new Request(`https://live-news.cache/${encodeURIComponent(`${tbs}|${q.toLowerCase()}`)}`);
  const hit = await cache?.match(cacheKey).catch(() => undefined);
  if (hit) return hit.json();

  try {
    const json = await post(env, "search",
      { query: q, limit: SEARCH_LIMIT, sources: ["news"], tbs, country: "vn" }, SEARCH_TIMEOUT_MS);
    const raw: any[] = json?.data?.news ?? [];
    const items: NewsItem[] = raw
      .filter((r) => typeof r?.url === "string" && typeof r?.title === "string")
      .map((r) => ({ title: r.title, url: r.url, source: hostOf(r.url), date: r.date ?? "", content: "" }));
    const top = Math.max(0, Number(env.FIRECRAWL_SCRAPE_TOP ?? "2") || 0);
    const contents = await Promise.all(items.slice(0, top).map((it) => scrapeContent(env, it.url)));
    contents.forEach((c, i) => (items[i].content = c));
    if (items.length && cache) {
      const resp = new Response(JSON.stringify(items), {
        headers: { "Content-Type": "application/json", "Cache-Control": `max-age=${CACHE_TTL_S}` },
      });
      await cache.put(cacheKey, resp).catch(() => undefined);
    }
    return items;
  } catch (e) {
    console.warn(`Tìm tin web lỗi: ${(e as Error).message}`);
    return [];
  }
}
