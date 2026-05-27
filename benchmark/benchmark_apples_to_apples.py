"""
Benchmark apple-to-apple: cùng input baseline → so tốc độ Python vs Spark.

Input: `data/education_comments_new.json` + `data/showbiz_comments_new.json`
       (cùng nguồn `Analyze keywords.py` đã dùng để sinh
       `data/keyword_analysis_v4.json`).

Đo wall-clock cho:
  - Python single-thread: gọi trực tiếp `Analyze keywords.py::analyze_file`
  - Spark `local[N]`: nạp JSON list → DataFrame → analyze()

Output: `data/spark/benchmark_apples.json`
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EDU_JSON = PROJECT_ROOT / "data/raw/education_comments_new.json"
SHOW_JSON = PROJECT_ROOT / "data/raw/showbiz_comments_new.json"
BASELINE_PY = PROJECT_ROOT / "analysis/single/Analyze keywords.py"
OUT_FILE = PROJECT_ROOT / "benchmark/benchmark_apples.json"


def load_baseline_module():
    spec = importlib.util.spec_from_file_location("baseline_pmi", BASELINE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def benchmark_python_single() -> dict:
    base = load_baseline_module()
    timings = {}
    for label, path in [("education", EDU_JSON), ("showbiz", SHOW_JSON)]:
        t0 = time.perf_counter()
        result = base.analyze_file(str(path), pmi_min_count=3, pmi_threshold=1.0)
        base.top_keywords(result, top_n=10)
        timings[label] = round(time.perf_counter() - t0, 2)
    timings["total"] = round(timings["education"] + timings["showbiz"], 2)
    return timings


def benchmark_spark(n_threads: int) -> dict:
    """Nạp JSON list vào Spark DataFrame, chạy analyze()."""
    from preprocessing.spark.spark_session_factory import get_spark
    from analysis.spark.pyspark_pmi_keywords import analyze
    from pyspark.sql import types as T

    spark = get_spark(app_name=f"bench-apples-{n_threads}", n_threads=n_threads)
    spark.sparkContext.setLogLevel("WARN")

    schema = T.StructType([
        T.StructField("comment_id", T.StringType()),
        T.StructField("text", T.StringType()),
        T.StructField("id_content", T.StringType()),
    ])

    timings = {}
    try:
        for label, path, marker in [
            ("education", EDU_JSON, "education"),
            ("showbiz", SHOW_JSON, "showbiz"),
        ]:
            with open(path, encoding="utf-8") as f:
                items = json.load(f)
            # Suy id_content từ comment_id giống logic baseline
            rows = []
            for it in items:
                cid = it.get("comment_id", "")
                # cmt_education_001_0001 → education_001
                parts = cid.replace("cmt_", "").split("_")
                idc = "_".join(parts[:2]) if len(parts) >= 2 else cid
                rows.append({
                    "comment_id": cid,
                    "text": it.get("text", ""),
                    "id_content": idc,
                })

            tmp_dir = PROJECT_ROOT / "benchmark/_apples_tmp"
            tmp_dir.mkdir(exist_ok=True, parents=True)
            tmp_parquet = tmp_dir / label
            (
                spark.createDataFrame(rows, schema)
                .repartition(max(spark.sparkContext.defaultParallelism, 4))
                .write.mode("overwrite")
                .parquet(str(tmp_parquet.resolve()))
            )

            t0 = time.perf_counter()
            res = analyze(spark, str(tmp_parquet.resolve()), None,
                          min_count=3, min_pmi=1.0, top_n=10)
            timings[label] = round(time.perf_counter() - t0, 2)
            timings[f"{label}_n_docs"] = res["n_docs"]
    finally:
        spark.stop()

    timings["total"] = round(timings["education"] + timings["showbiz"], 2)
    return timings


def main():
    print("=== Apple-to-apple benchmark ===")
    print(f"  Education: {EDU_JSON.name}")
    print(f"  Showbiz:   {SHOW_JSON.name}")

    print("\n--- Python single-thread ---")
    py = benchmark_python_single()
    print(f"  edu={py['education']}s  show={py['showbiz']}s  total={py['total']}s")

    results = {"python_single": py, "spark_runs": []}
    for n in [1, 2, 4, -1]:
        label = f"local[{n}]" if n > 0 else "local[*]"
        print(f"\n--- Spark {label} ---")
        r = benchmark_spark(n)
        r["label"] = label
        r["speedup_vs_python"] = round(py["total"] / r["total"], 2)
        results["spark_runs"].append(r)
        print(f"  edu={r['education']}s  show={r['showbiz']}s  "
              f"total={r['total']}s  speedup={r['speedup_vs_python']}x")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    print(f"  Python single-thread total:  {py['total']:>6.2f}s")
    for r in results["spark_runs"]:
        print(f"  Spark {r['label']:11s}  total={r['total']:>6.2f}s  "
              f"speedup={r['speedup_vs_python']}x")
    print(f"\n[OK] saved → {OUT_FILE}")


if __name__ == "__main__":
    main()
