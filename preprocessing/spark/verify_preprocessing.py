"""
Verify Spark preprocessing output match Python single-thread baseline.

So sánh count + tập comment_id giữ lại:
  - Spark: đọc Parquet đã ghi từ pyspark_preprocessing
  - Baseline: chạy is_trash trực tiếp trên flattened JSON

Pass khi: Jaccard(spark_ids, baseline_ids) == 1.0 (deterministic, không nên lệch).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.spark.is_trash_rule import is_trash
from preprocessing.spark.spark_session_factory import get_spark


INPUT_DIRS = [
    PROJECT_ROOT / "data/processed/process_education/cleaned_data_input",
    PROJECT_ROOT / "data/processed/process_showbiz/input_clean_data",
]
PARQUET_DIR = PROJECT_ROOT / "data/spark-output/clean"


def baseline_kept_ids() -> set[str]:
    kept = set()
    for d in INPUT_DIRS:
        for fp in sorted(d.glob("*.json")):
            with fp.open(encoding="utf-8") as f:
                obj = json.load(f)
            if not isinstance(obj, dict) or "comments" not in obj:
                continue
            for c in obj.get("comments") or []:
                if not is_trash(c.get("text")):
                    kept.add(c.get("comment_id"))
                for r in c.get("replies") or []:
                    if not is_trash(r.get("text")):
                        kept.add(r.get("comment_id"))
    return kept


def spark_kept_ids() -> set[str]:
    spark = get_spark(app_name="verify-preprocess", n_threads=2)
    spark.sparkContext.setLogLevel("WARN")
    try:
        df = spark.read.parquet(str(PARQUET_DIR.resolve()))
        rows = df.select("comment_id").collect()
    finally:
        spark.stop()
    return {r["comment_id"] for r in rows}


def main():
    print("Computing baseline kept ids ...")
    base = baseline_kept_ids()
    print(f"  baseline: {len(base)} comments")

    print("Reading Spark Parquet ...")
    spark_ids = spark_kept_ids()
    print(f"  spark:    {len(spark_ids)} comments")

    only_base = base - spark_ids
    only_spark = spark_ids - base
    union = base | spark_ids
    inter = base & spark_ids
    jaccard = len(inter) / len(union) if union else 1.0

    print(f"\n  intersection: {len(inter)}")
    print(f"  only baseline: {len(only_base)}")
    print(f"  only spark:    {len(only_spark)}")
    print(f"  jaccard: {jaccard:.6f}")

    if only_base or only_spark:
        print("\n[FAIL] Mismatch detected.")
        for cid in list(only_base)[:5]:
            print(f"  baseline-only: {cid}")
        for cid in list(only_spark)[:5]:
            print(f"  spark-only:    {cid}")
        sys.exit(1)
    print("\n[OK] Spark output matches baseline 1:1")


if __name__ == "__main__":
    main()
