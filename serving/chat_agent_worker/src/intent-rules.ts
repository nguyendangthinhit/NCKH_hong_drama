// Nhận diện ý định bằng luật (không gọi LLM) và các câu trả lời cố định. Port của intent_rules.py.
import { normalized } from "./text-normalizer";

export const INFO_REPLY =
  "Mình là Drama Intelligence Bot 🎭 Mình có thể giúp bạn: tìm hiểu diễn biến các drama " +
  "Giáo dục & Showbiz nổi bật, xem dư luận cộng đồng phản ứng thế nào, và xem thống kê " +
  "toàn hệ thống. Bạn muốn tìm hiểu sự kiện nào?";
export const GREETING_REPLY =
  "Chào bạn 👋 Mình là Drama Intelligence Bot, chuyên tổng hợp các drama Giáo dục và " +
  "Showbiz. Bạn muốn tìm hiểu sự kiện nào, hay xem các vụ đang được quan tâm nhất?";
export const SPAM_REPLY =
  "Mình xin phép không phản hồi nội dung này. Nếu bạn muốn tìm hiểu drama nào, cứ hỏi mình nhé.";
export const UNRELATED_REPLY =
  "Câu này nằm ngoài phạm vi của mình rồi. Mình chỉ hỗ trợ thông tin về các drama Giáo dục " +
  "và Showbiz cùng phản ứng dư luận. Bạn muốn hỏi sự kiện nào?";
export const CLARIFY_REPLY =
  "Bạn có thể cho mình biết cụ thể tên nhân vật hoặc sự kiện bạn đang tìm không? " +
  "Hiện mình chưa thấy thông tin khớp trong dữ liệu.";

const phrases = (text: string): string[] =>
  text.split("\n").map((p) => p.trim()).filter(Boolean);

const GREETING_WORDS = new Set("hello hi hey alo chao xin ban nhe a oi bot ad admin ha lo".split(" "));
const INFO = phrases(`ban la ai
ban la gi
ban lam duoc gi
ban giup duoc gi
ban co the lam gi
chuc nang
huong dan su dung
gioi thieu ve ban`);
// Tục tĩu: so trên chữ thường CÒN dấu. \w của JS chỉ là ASCII nên dùng lớp Unicode thay cho \w.
const W = "[\\p{L}\\p{N}_]";
const PROFANITY = new RegExp(
  `(?<!${W})(đm|đmm|dmm|dcm|đcm|vcl|vkl|vl|cc|clm|đéo|địt|đụ|lồn|cặc|buồi|óc chó|ngu như)(?!${W})`,
  "u",
);
const TOP = phrases(`top
hot
noi bat
quan tam nhat
nhieu nhat
gay bao
danh sach
co drama
co nhung drama
co vu nao
co su kien nao
drama nao
vu nao dang
su kien nao dang`);
const STATS = phrases(`thong ke
tong so
bao nhieu su kien
bao nhieu vu
ty le
ti le
binh luan rac
toan he thong
so lieu`);
const OPINION = phrases(`du luan
cam xuc
phan ung
cong dong
dan mang
nghi gi
nghi sao
binh luan
tich cuc
tieu cuc
thai do`);
const FOLLOWUP = phrases(`vu do
vu nay
su kien do
su kien nay
nguoi do
nguoi nay
anh ay
co ay
ong ay
ba ay
ho
sau do
roi sao
the con
ket qua
tiep theo
chi tiet hon
cu the hon
noi them`);
const DRAMA = phrases(`drama
su kien
vu
scandal
on ao
phot
to
tranh cai
bi bat
khoi to
lum xum
bi che
showbiz
giao duc
ca si`);
const EDUCATION_HINTS = phrases("giao duc\ntruong\nhoc sinh\nsinh vien\ngiao vien\nthi");
const SHOWBIZ_HINTS = phrases("showbiz\ngiai tri\nca si\ndien vien\nnghe si\nkol\ntiktoker\nstreamer\nrapper");

const hasPhrase = (norm: string, list: string[]): boolean => {
  const padded = ` ${norm} `;
  return list.some((p) => padded.includes(` ${p} `));
};

export const isSpam = (m: string): boolean => !normalized(m) || PROFANITY.test(m.toLowerCase());
export const isGreetingOnly = (m: string): boolean => {
  const toks = normalized(m).split(" ").filter(Boolean);
  return toks.length > 0 && toks.length <= 5 && toks.every((t) => GREETING_WORDS.has(t));
};
export const isInfo = (m: string): boolean => hasPhrase(normalized(m), INFO);
export const isTopRequest = (m: string): boolean => hasPhrase(normalized(m), TOP);
export const isStatsRequest = (m: string): boolean => hasPhrase(normalized(m), STATS);
export const isOpinionRequest = (m: string): boolean => hasPhrase(normalized(m), OPINION);
export const isFollowup = (m: string): boolean => hasPhrase(normalized(m), FOLLOWUP);
export const mentionsDrama = (m: string): boolean => hasPhrase(normalized(m), DRAMA);

/** "education" / "showbiz" nếu câu hỏi nói rõ lĩnh vực, ngược lại null. */
export function categoryHint(m: string): "education" | "showbiz" | null {
  const norm = normalized(m);
  const edu = hasPhrase(norm, EDUCATION_HINTS);
  const show = hasPhrase(norm, SHOWBIZ_HINTS);
  if (edu === show) return null;
  return edu ? "education" : "showbiz";
}
