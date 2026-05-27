"""
PMI keyword extraction trong PySpark.

Pipeline:
  Parquet (clean comments) → tokenize UDF → uni/bi/tri-grams →
  count → PMI → score = freq × log2(1+max(pmi,0)) → top-N

Match logic của `data/Analyze keywords.py` (v4) trên cùng dataset
để verify reproducibility.

Run:
    python data/spark/pyspark_pmi_keywords.py \
        --parquet data/spark/clean \
        --output data/spark/keyword_analysis_spark.json \
        --top 10
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from data.spark.spark_session_factory import get_spark
from data.spark.text_tokenizer import tokenize, tokenize_strip

# Stopwords copy từ Analyze keywords.py (v4) — giữ nguyên để PMI match baseline
STOPWORDS = {
    "và", "của", "là", "có", "cho", "trong", "với", "được", "không",
    "này", "đó", "thì", "mà", "để", "hay", "hoặc", "những", "các", "một",
    "về", "như", "theo", "lại", "đã", "sẽ", "bị", "vì", "khi", "nếu",
    "còn", "cũng", "đây", "đâu", "từ", "ra", "vào", "lên", "xuống", "qua",
    "nên", "do", "vậy", "dù", "tuy", "nhưng", "song", "thế",
    "trước", "sau", "trên", "dưới", "giữa", "bên", "ngoài", "gần", "xa",
    "tôi", "mình", "bạn", "em", "anh", "chị", "họ", "người", "mọi",
    "ta", "chúng", "nó", "tụi", "bọn", "ai", "gì", "nào",
    "kia", "ấy", "tui", "tao", "mày", "hắn", "y",
    "cháu", "chú", "cô", "bác", "ông", "bà", "thầy", "con",
    "rất", "quá", "thật", "thôi", "đi", "ơi", "nhỉ", "nhé", "ạ", "à",
    "ừ", "uh", "ok", "okay", "oke", "nha", "nè", "ne", "ha", "hả",
    "rồi", "nhiều", "mới", "mấy", "chứ", "lắm", "chưa", "giờ", "thêm",
    "luôn", "vẫn", "đang", "đến", "đều", "chỉ", "cả", "hết",
    "thiệt", "thực", "đúng", "sai", "khác", "riêng",
    "cứ", "mỗi", "tất", "bao", "bất", "lần", "lúc",
    "nhau", "cùng", "xong", "xem",
    "sao", "nữa", "đừng",
    "yêu", "thích", "ghét", "buồn", "vui", "sợ", "tức",
    "cười", "khóc", "nhìn", "nghe", "nói", "làm", "biết", "thấy",
    "nghĩ", "hiểu", "muốn", "cần", "phải",
    "hát", "chơi", "tươi", "đẹp", "xấu", "tốt", "kém",
    "nhà", "lớp", "việc", "cái", "bài", "cách",
    "kiểu", "loại", "dạng", "chuyện", "điều",
    "năm", "tháng", "ngày", "hôm", "tuần",
    "ôi", "wow", "haha", "hihi", "hehe", "hm", "hmm", "ừm",
    "ah", "oh", "ui", "ủa", "ờ", "ơ",
}


# ─── UDF & helpers ───────────────────────────────────────────────────────────

tokenize_udf = F.udf(tokenize, T.ArrayType(T.StringType()))
tokenize_strip_udf = F.udf(tokenize_strip, T.ArrayType(T.StringType()))


def _is_valid_token(t: str) -> bool:
    """Match `is_valid_token` ở baseline."""
    import re
    if t is None or len(t) < 3:
        return False
    if t.lower() in STOPWORDS:
        return False
    if t.startswith("http") or t.startswith("www"):
        return False
    if re.fullmatch(r"[\d\W_]+", t):
        return False
    return True


# ─── Pipeline ────────────────────────────────────────────────────────────────

def add_tokens(df: DataFrame, strip_names: bool = False) -> DataFrame:
    udf = tokenize_strip_udf if strip_names else tokenize_udf
    return df.withColumn("tokens", udf(F.col("text")))


def unigram_counts(tokens_df: DataFrame) -> DataFrame:
    """Đếm unigram, không filter ở đây để giữ total cho PMI."""
    return (
        tokens_df.select(F.explode("tokens").alias("w"))
        .groupBy("w")
        .agg(F.count("*").alias("c"))
    )


def ngram_counts(tokens_df: DataFrame, n: int) -> DataFrame:
    """
    Sliding window n-gram qua RDD.flatMap (đơn giản hơn dùng Window cho mỗi token).

    Trả DataFrame [phrase, c].
    """
    rdd = tokens_df.select("tokens").rdd.flatMap(
        lambda row: (
            " ".join(row["tokens"][i:i + n])
            for i in range(len(row["tokens"]) - n + 1)
        ) if row["tokens"] else []
    )
    return rdd.map(lambda p: (p, 1)).reduceByKey(lambda a, b: a + b).toDF(["phrase", "c"])


def compute_bigram_pmi(
    bigram_df: DataFrame,
    unigram_df: DataFrame,
    total_uni: int,
    total_bi: int,
    min_count: int,
    min_pmi: float,
) -> dict[str, float]:
    """
    Collect bigram counts về driver rồi compute PMI giống baseline.

    Tránh self-join phức tạp + đảm bảo float math khớp 100% với baseline.
    """
    uni_map = {r["w"]: r["c"] for r in unigram_df.collect()}
    bi_rows = bigram_df.filter(F.col("c") >= min_count).collect()

    pmi: dict[str, float] = {}
    for r in bi_rows:
        phrase, cnt = r["phrase"], r["c"]
        parts = phrase.split(" ", 1)
        if len(parts) != 2:
            continue
        w1, w2 = parts
        if w1 in STOPWORDS or w2 in STOPWORDS:
            continue
        if not _is_valid_token(w1) or not _is_valid_token(w2):
            continue
        c1 = uni_map.get(w1, 0)
        c2 = uni_map.get(w2, 0)
        if c1 == 0 or c2 == 0:
            continue
        p12 = cnt / total_bi
        p1 = c1 / total_uni
        p2 = c2 / total_uni
        score = math.log2(p12 / (p1 * p2))
        if score >= min_pmi:
            pmi[phrase] = score
    return pmi


def compute_trigram_pmi(
    trigram_df: DataFrame,
    bigram_pmi: dict[str, float],
    min_count: int,
) -> dict[str, float]:
    """Trigram chỉ giữ nếu cả 2 bigram con đều high-PMI; score = avg."""
    rows = trigram_df.filter(F.col("c") >= min_count).collect()
    out: dict[str, float] = {}
    for r in rows:
        phrase = r["phrase"]
        parts = phrase.split(" ")
        if len(parts) != 3:
            continue
        if parts[0] in STOPWORDS or parts[-1] in STOPWORDS:
            continue
        if not all(_is_valid_token(p) for p in parts):
            continue
        b1 = " ".join(parts[:2])
        b2 = " ".join(parts[1:])
        if b1 in bigram_pmi and b2 in bigram_pmi:
            out[phrase] = (bigram_pmi[b1] + bigram_pmi[b2]) / 2
    return out


def collect_freq_per_id(
    tokens_df: DataFrame,
    high_pmi_phrases: set[str],
) -> dict[str, dict[str, int]]:
    """
    Đếm freq từng phrase theo id_content, giống pass-2 ở baseline.

    Trả {token: {id_content: count}}. Logic:
      - Match trigram trước → đánh dấu position → bigram → unigram
      - Suppress unigram nếu nó nằm trong set words cấu thành PMI phrase
    """
    suppressed = {w for phrase in high_pmi_phrases for w in phrase.split()}
    rows = tokens_df.select("id_content", "tokens").collect()

    freq: dict[str, dict[str, int]] = {}
    for row in rows:
        cid = row["id_content"]
        toks = row["tokens"] or []
        matched = set()

        # Trigram
        for i in range(len(toks) - 2):
            phrase = " ".join(toks[i:i + 3])
            if phrase in high_pmi_phrases:
                freq.setdefault(phrase, {}).setdefault(cid, 0)
                freq[phrase][cid] += 1
                matched.update([i, i + 1, i + 2])

        # Bigram
        for i in range(len(toks) - 1):
            phrase = " ".join(toks[i:i + 2])
            if phrase in high_pmi_phrases:
                freq.setdefault(phrase, {}).setdefault(cid, 0)
                freq[phrase][cid] += 1
                matched.update([i, i + 1])

        # Unigram
        for i, tok in enumerate(toks):
            if i in matched or tok in suppressed:
                continue
            if _is_valid_token(tok):
                freq.setdefault(tok, {}).setdefault(cid, 0)
                freq[tok][cid] += 1

    return freq


def weighted_score(freq: int, pmi: float) -> float:
    return freq * math.log2(1 + max(pmi, 0))


def top_keywords(
    freq_map: dict[str, dict[str, int]],
    pmi_scores: dict[str, float],
    top_n: int,
) -> list[dict]:
    """Format giống baseline `data/keyword_analysis_v4.json` để dễ so sánh."""
    ngram_label = {1: "unigram", 2: "bigram", 3: "trigram"}
    scored = []
    for token, counter in freq_map.items():
        f = sum(counter.values())
        p = pmi_scores.get(token, 0.0)
        # `details` sort giảm dần theo count để báo cáo đẹp
        details = dict(sorted(counter.items(), key=lambda kv: kv[1], reverse=True))
        scored.append({
            "keyword": token,
            "ngram_type": ngram_label[min(len(token.split()), 3)],
            "total_frequency": f,
            "total_articles": len(counter),
            "pmi_score": round(p, 2),
            "score": round(weighted_score(f, p), 1),
            "details": details,
        })
    return sorted(scored, key=lambda r: r["score"], reverse=True)[:top_n]


# ─── Driver ──────────────────────────────────────────────────────────────────

def analyze(
    spark: SparkSession,
    parquet_path: str,
    domain_filter: str | None,
    min_count: int,
    min_pmi: float,
    top_n: int,
    strip_names: bool = False,
) -> dict:
    """
    Chạy phân tích cho 1 domain (education hoặc showbiz).

    `domain_filter`: substring trong id_content, vd "education" hoặc "showbiz".
    `strip_names`: True nếu loại tag tên Facebook đầu comment.
    """
    t0 = time.perf_counter()
    df = spark.read.parquet(parquet_path)
    if domain_filter:
        df = df.filter(F.col("id_content").contains(domain_filter))

    tokens_df = add_tokens(df, strip_names=strip_names).select("id_content", "tokens").cache()
    n_docs = tokens_df.count()

    t1 = time.perf_counter()

    # Counts ở Spark
    uni_df = unigram_counts(tokens_df)
    total_uni = tokens_df.select(F.explode("tokens").alias("w")).count()

    bi_df = ngram_counts(tokens_df, 2)
    total_bi = bi_df.agg(F.sum("c")).collect()[0][0] or 0

    tri_df = ngram_counts(tokens_df, 3)

    t2 = time.perf_counter()

    # PMI ở driver
    bi_pmi = compute_bigram_pmi(bi_df, uni_df, total_uni, total_bi, min_count, min_pmi)
    tri_pmi = compute_trigram_pmi(tri_df, bi_pmi, min_count)
    all_pmi = {**bi_pmi, **tri_pmi}

    t3 = time.perf_counter()

    # Freq per id_content
    freq_map = collect_freq_per_id(tokens_df, set(all_pmi.keys()))

    t4 = time.perf_counter()

    top = top_keywords(freq_map, all_pmi, top_n)

    tokens_df.unpersist()

    return {
        "domain": domain_filter or "all",
        "n_docs": n_docs,
        "n_high_pmi": len(all_pmi),
        "top": top,
        "timings_sec": {
            "tokenize": round(t1 - t0, 2),
            "ngram_count": round(t2 - t1, 2),
            "pmi": round(t3 - t2, 2),
            "freq_per_id": round(t4 - t3, 2),
            "total": round(t4 - t0, 2),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--min-count", type=int, default=3)
    parser.add_argument("--min-pmi", type=float, default=1.0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--strip-names", action="store_true",
                        help="Loại tag tên Facebook đầu comment trước khi tokenize")
    args = parser.parse_args()

    spark = get_spark(app_name="pmi-keywords", n_threads=args.threads)
    spark.sparkContext.setLogLevel("WARN")

    parquet_path = str(Path(args.parquet).resolve())

    try:
        out = {"EDUCATION": [], "SHOWBIZ": []}
        meta = {
            "min_count": args.min_count,
            "min_pmi": args.min_pmi,
            "top_n": args.top,
            "n_docs_per_domain": {},
            "timings_sec": {},
        }
        for domain in ["education", "showbiz"]:
            print(f"\n=== {domain.upper()} ===")
            res = analyze(
                spark, parquet_path, domain, args.min_count,
                args.min_pmi, args.top, strip_names=args.strip_names,
            )
            out[domain.upper()] = res["top"]
            meta["n_docs_per_domain"][domain] = res["n_docs"]
            meta["timings_sec"][domain] = res["timings_sec"]
            for r in res["top"]:
                print(f"  {r['score']:7.1f}  {r['keyword']:30s}  "
                      f"freq={r['total_frequency']:5d}  "
                      f"articles={r['total_articles']:2d}  "
                      f"pmi={r['pmi_score']:.2f}")
    finally:
        spark.stop()

    out["_meta"] = meta
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)
    print(f"\n[OK] saved → {args.output}")


if __name__ == "__main__":
    main()
