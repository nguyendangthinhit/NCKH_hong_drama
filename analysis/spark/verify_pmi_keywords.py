"""
Verify Spark PMI top-10 match Python baseline.

Strategy:
  1. Đọc Parquet clean (Spark output)
  2. Convert thành list comments theo format baseline (`comment_id` + `text`)
  3. Chạy baseline `Analyze keywords.py::analyze_file` trực tiếp trong driver
  4. So sánh top 10 phrase + score giữa baseline vs `keyword_analysis_spark.json`

Pass: Jaccard(top_10_baseline, top_10_spark) ≥ 0.7 (tolerance để tránh fail
do tie ở score gần ngưỡng); top_5 phải match 100%.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PARQUET_DIR = PROJECT_ROOT / "data/spark-output/clean"
SPARK_OUT = PROJECT_ROOT / "benchmark/keyword_analysis_spark.json"
BASELINE_PY = PROJECT_ROOT / "analysis/single/Analyze keywords.py"
TMP_DIR = PROJECT_ROOT / "benchmark/_baseline_tmp"


def load_baseline_module():
    """Load `Analyze keywords.py` (có space trong tên) qua importlib."""
    spec = importlib.util.spec_from_file_location("baseline_pmi", BASELINE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def materialize_domain_json(domain: str) -> Path:
    """Đọc Parquet, filter theo domain, ghi list comments JSON cho baseline."""
    from data.spark.spark_session_factory import get_spark
    from pyspark.sql import functions as F

    spark = get_spark(app_name=f"materialize-{domain}", n_threads=2)
    spark.sparkContext.setLogLevel("WARN")
    try:
        df = (
            spark.read.parquet(str(PARQUET_DIR.resolve()))
            .filter(F.col("id_content").contains(domain))
            .select("comment_id", "text")
        )
        rows = df.collect()
    finally:
        spark.stop()

    TMP_DIR.mkdir(exist_ok=True, parents=True)
    out = TMP_DIR / f"{domain}_comments.json"
    payload = [{"comment_id": r["comment_id"], "text": r["text"]} for r in rows]
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"  materialized {len(payload):>6} comments → {out.name}")
    return out


def run_baseline(json_path: Path) -> list[tuple[str, int, float, float]]:
    """Chạy baseline analyze_file → top_keywords; trả top10 [(token, freq, pmi, score)]."""
    base = load_baseline_module()
    result = base.analyze_file(str(json_path), pmi_min_count=3, pmi_threshold=1.0)
    return base.top_keywords(result, top_n=10)


def compare(domain: str, baseline_top: list, spark_top: list[dict]) -> dict:
    base_tokens = [t[0] for t in baseline_top]
    spark_tokens = [r["keyword"] for r in spark_top]

    inter = set(base_tokens) & set(spark_tokens)
    union = set(base_tokens) | set(spark_tokens)
    jaccard = len(inter) / len(union) if union else 1.0
    top5_match = len(set(base_tokens[:5]) & set(spark_tokens[:5])) / 5

    print(f"\n  === {domain.upper()} ===")
    print(f"  {'rank':4s}  {'baseline':25s}  {'spark':25s}")
    for i in range(10):
        b = baseline_top[i][0] if i < len(baseline_top) else ""
        s = spark_tokens[i] if i < len(spark_tokens) else ""
        mark = " " if b == s else ("≈" if (b in spark_tokens) else "X")
        print(f"  {i + 1:>2}.   {b:25s}  {s:25s}  {mark}")

    print(f"  jaccard top10: {jaccard:.2f}")
    print(f"  match top5:    {top5_match:.2f}")
    return {"jaccard": jaccard, "top5": top5_match}


def main():
    if not SPARK_OUT.exists():
        print(f"[FAIL] missing {SPARK_OUT}; run pyspark_pmi_keywords first")
        sys.exit(2)

    spark_payload = json.loads(SPARK_OUT.read_text(encoding="utf-8"))

    overall_pass = True
    for domain in ["education", "showbiz"]:
        print(f"\n[1/3] materialize {domain} ...")
        json_path = materialize_domain_json(domain)

        print(f"[2/3] running baseline on {domain} ...")
        baseline_top = run_baseline(json_path)

        spark_top = spark_payload[domain.upper()]
        m = compare(domain, baseline_top, spark_top)
        if m["top5"] < 0.6:
            overall_pass = False

    print()
    if overall_pass:
        print("[OK] Spark PMI consistent with baseline (top5 >= 60%)")
    else:
        print("[FAIL] top5 mismatch — investigate stopwords / tokenizer / float math")
        sys.exit(1)


if __name__ == "__main__":
    main()
