// Chuẩn hoá tiếng Việt để so khớp: bỏ dấu, chữ thường, tách từ, sinh bigram. Port của text_normalizer.py.

const ABBREVIATIONS: Record<string, string> = {
  khkt: "khoa hoc ky thuat",
  tphcm: "ho chi minh",
  hcm: "ho chi minh",
  gv: "giao vien",
  hs: "hoc sinh",
  sv: "sinh vien",
  dh: "dai hoc",
  bgd: "bo giao duc",
  j97: "jack",
};

const STOPWORDS = new Set(
  `a ah ai anh ay ban bao biet bi bo cac cai cho chu chuyen co cua cung da dang
   day de den di do drama duoc gi gioi hay hien ho hoi khi khong kia la lam lai luc
   ma minh mot moi nao nay ne neu nghe nguoi nha nhe nhieu nhu nhung o oi ra roi sao
   se su kien tai the thi thong tin toi tu va ve vi viec voi vu xay xin
   top hot nhat chao hello hi tin tuc cap nhat`
    .split(/\s+/)
    .filter(Boolean),
);

const NON_WORD = /[^a-z0-9]+/;

export function stripAccents(text: string): string {
  return text.toLowerCase().replace(/đ/g, "d").normalize("NFD").replace(/\p{Mn}/gu, "");
}

export function tokenize(text: string, dropStopwords = true): string[] {
  const tokens: string[] = [];
  for (const tok of stripAccents(text).split(NON_WORD)) {
    if (!tok) continue;
    tokens.push(...(ABBREVIATIONS[tok] ?? tok).split(" "));
  }
  return dropStopwords ? tokens.filter((t) => !STOPWORDS.has(t)) : tokens;
}

/** Tập unigram + bigram dùng để chấm điểm khớp. */
export function terms(text: string): Set<string> {
  const toks = tokenize(text, false);
  const out = new Set<string>();
  for (const t of toks) if (!STOPWORDS.has(t)) out.add(t);
  for (let i = 0; i + 1 < toks.length; i++) {
    const [a, b] = [toks[i], toks[i + 1]];
    if (!(STOPWORDS.has(a) && STOPWORDS.has(b))) out.add(`${a} ${b}`);
  }
  return out;
}

/** Chuỗi đã bỏ dấu, gộp khoảng trắng: dùng cho so khớp cụm từ khoá. */
export function normalized(text: string): string {
  return stripAccents(text).split(NON_WORD).filter(Boolean).join(" ");
}
