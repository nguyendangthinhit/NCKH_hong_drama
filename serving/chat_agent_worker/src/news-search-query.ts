// Dựng câu tìm tin cho Firecrawl/Google News: câu hỏi văn nói ("drama nào đang hot gần đây") gần như
// không ra kết quả, nên rút về từ khoá (giữ dấu, giữ tên riêng). Port: serving/chat_agent/news_search_query.py.
import { categoryHint } from "./intent-rules";
import { normalized, stripAccents } from "./text-normalizer";

// Cụm hỏi/chỉ thời gian (đã bỏ dấu) bị cắt khỏi câu tìm. Bỏ theo CỤM để không xoá nhầm tên riêng
// (vd "hiện" trong "Hiền Hồ", "nhật" trong "Nhật Kim Anh").
const STOP_PHRASES = `moi nhat|gan day|gan nhat|moi day|vua roi|vua xay ra|hom nay|hom qua|tuan nay|thang nay
|dao nay|hien tai|hien gio|bay gio|luc nay|tin moi|co gi moi|cap nhat|dien bien moi|dang hot|ra sao roi
|the nao roi|the nao|ra sao|su kien|tin tuc|thong tin|quan tam nhat|noi bat|gay bao|on ao|lum xum
|tren mang|dan mang|cho minh|cho toi|cho hoi`
  .split("|").map((p) => p.trim().split(" "));
// Từ đơn để bỏ: so CÓ DẤU (chữ thường) vì bỏ dấu thì "có" trùng "cô" (cô giáo), "bị" trùng "Bí"...
const STOP_WORDS = new Set(
  "à ạ ai ấy bị biết các có của đang đó drama được gì hay hot không ko là mới này nào nè nhé những nữa ơi phốt rồi scandal thế thêm thì tin về với vậy vụ xem".split(" "),
);

const GENERIC_QUERY = { showbiz: "ồn ào showbiz Việt", education: "giáo dục gây xôn xao" } as const;

const clean = (tok: string): string => tok.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "");
const norm = (tok: string): string => stripAccents(tok).replace(/[^a-z0-9]/g, "");

// Khớp cả câu để không kéo chủ thể mới (vd "Điện Biên có gì mới") về sự kiện cũ.
const SUBJECTLESS_LATEST = /^(?:(?:vay thi|the thi|the con|vay|the|roi|con) )?(?:co )?(?:them )?(?:(?:dien bien|thong tin|tin tuc|tin|tinh tiet) )?(?:(?:gi|nao) )?moi(?: nua)?(?: (?:khong|ko))?(?: (?:nhi|nhe|a))?$/;

/** Câu hỏi cập nhật không nêu chủ thể; cần sự kiện từ phiên hoặc hỏi lại tên. */
export const isSubjectlessLatestRequest = (message: string): boolean => SUBJECTLESS_LATEST.test(normalized(message));

/** Từ khoá giữ dấu của câu hỏi, đã bỏ cụm hỏi/chỉ thời gian. */
export function searchKeywords(message: string): string {
  const toks = message.split(/\s+/).map(clean).filter(Boolean);
  const norms = toks.map(norm);
  const keep: string[] = [];
  for (let i = 0; i < toks.length; ) {
    const phrase = STOP_PHRASES.find((p) => p.every((w, j) => norms[i + j] === w));
    if (phrase) {
      i += phrase.length;
      continue;
    }
    if (!STOP_WORDS.has(toks[i].toLowerCase().normalize("NFC"))) keep.push(toks[i]);
    i++;
  }
  return keep.join(" ");
}

const MAX_QUERY_WORDS = 6; // câu tìm dài (cả tiêu đề) thì Google News gần như không trả kết quả
const wordCount = (s: string): number => s.split(" ").filter(Boolean).length;
const onlyCategory = (kw: string): boolean => !kw || (categoryHint(kw) !== null && wordCount(kw) <= 2);

/** Câu hỏi không nêu chủ thể cụ thể (chỉ còn tên lĩnh vực hoặc không còn gì), vd "drama giáo dục gần đây". */
export const isGenericQuestion = (message: string): boolean => onlyCategory(searchKeywords(message));

/** Câu tìm cho câu hỏi không khớp sự kiện local. Chỉ còn tên lĩnh vực -> câu tìm chung theo lĩnh vực. */
export function buildSearchQuery(message: string): string {
  const kw = searchKeywords(message);
  return onlyCategory(kw) ? GENERIC_QUERY[categoryHint(message) ?? "showbiz"] : kw;
}

/** Chủ thể của tiêu đề sự kiện: phần trước "–"/":" và tối đa 6 từ, vd "Jack (J97) – ..." -> "Jack J97". */
export function titleSubject(title: string): string {
  const subject = title.split(/\s[–-]\s|:/)[0].replace(/[()"“”'‘’]/g, " ");
  return subject.split(/\s+/).filter(Boolean).slice(0, MAX_QUERY_WORDS).join(" ");
}

/** Câu tìm cho sự kiện có sẵn. message = câu hỏi khớp trực tiếp sự kiện (vd "Shark Bình có gì mới"):
 * dùng từ khoá của nó nếu gọn; câu nối tiếp ("có gì mới không") thì không truyền -> chủ thể tiêu đề. */
export function eventSearchQuery(title: string, message?: string): string {
  const kw = message ? searchKeywords(message) : "";
  return !onlyCategory(kw) && wordCount(kw) <= MAX_QUERY_WORDS ? kw : titleSubject(title);
}
