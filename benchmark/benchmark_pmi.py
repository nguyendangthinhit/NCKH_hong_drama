"""
Benchmark Spark PMI pipeline ở các mức parallelism khác nhau,
so với Python single-thread baseline.

Đo wall-clock cho stage tokenize + n-gram count + PMI compute.
Lưu kết quả → `data/spark/benchmark_results.json`.

Run:
    python data/spark/benchmark_pmi.py
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

PARQUET_DIR = PROJECT_ROOT / "data/spark-output/clean"
TMP_DIR = PROJECT_ROOT / "benchmark/_baseline_tmp"
OUT_FILE = PROJECT_ROOT / "benchmark/benchmark_results.json"
BASELINE_PY = PROJECT_ROOT / "analysis/single/Analyze keywords.py"


def load_baseline_module():
    spec = importlib.util.spec_from_file_location("baseline_pmi", BASELINE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def materialize_full_dataset(scale: int = 1) -> Path:
    """Đọc Parquet, dump JSON cho baseline. `scale` x để show scaling curve."""
    from preprocessing.spark.spark_session_factory import get_spark

    spark = get_spark(app_name="materialize-full", n_threads=2)
    spark.sparkContext.setLogLevel("WARN")
    try:
        df = spark.read.parquet(str(PARQUET_DIR.resolve())).select("comment_id", "text")
        rows = df.collect()
    finally:
        spark.stop()

    payload = []
    for s in range(scale):
        for r in rows:
            payload.append({
                "comment_id": f"{r['comment_id']}_s{s}" if s > 0 else r["comment_id"],
                "text": r["text"],
            })

    TMP_DIR.mkdir(exist_ok=True, parents=True)
    suffix = "" if scale == 1 else f"_x{scale}"
    out = TMP_DIR / f"all_comments{suffix}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"  scale={scale}x: {len(payload)} comments → {out.name}")
    return out


def materialize_parquet_scaled(scale: int) -> Path:
    """Tạo bản Parquet x{scale} cho Spark (tránh duplicate ở driver)."""
    from preprocessing.spark.spark_session_factory import get_spark
    from pyspark.sql import functions as F

    out_dir = TMP_DIR / f"clean_x{scale}"
    if out_dir.exists():
        return out_dir

    spark = get_spark(app_name=f"scale-{scale}", n_threads=4)
    spark.sparkContext.setLogLevel("WARN")
    try:
        base = spark.read.parquet(str(PARQUET_DIR.resolve()))
        if scale == 1:
            scaled = base
        else:
            # Union nhiều bản với suffix khác nhau ở comment_id
            unions = []
            for s in range(scale):
                d = base.withColumn(
                    "comment_id",
                    F.concat(F.col("comment_id"), F.lit(f"_s{s}")) if s > 0 else F.col("comment_id"),
                )
                unions.append(d)
            scaled = unions[0]
            for d in unions[1:]:
                scaled = scaled.unionByName(d)
        scaled.write.mode("overwrite").parquet(str(out_dir.resolve()))
    finally:
        spark.stop()
    return out_dir


def benchmark_python_baseline(json_path: Path) -> float:
    base = load_baseline_module()
    t0 = time.perf_counter()
    result = base.analyze_file(str(json_path), pmi_min_count=3, pmi_threshold=1.0)
    base.top_keywords(result, top_n=10)
    return time.perf_counter() - t0


def benchmark_spark(parquet_path: str, n_threads: int) -> dict:
    """
    Chạy lại analyze() ở mức song song cho trước, đo total time.
    Tránh import vòng — gọi qua subprocess không cần thiết, cùng JVM ok.
    """
    from preprocessing.spark.spark_session_factory import get_spark
    from analysis.spark.pyspark_pmi_keywords import analyze

    spark = get_spark(app_name=f"bench-{n_threads}", n_threads=n_threads)
    spark.sparkContext.setLogLevel("WARN")

    timings = {}
    try:
        for domain in ["education", "showbiz"]:
            t0 = time.perf_counter()
            res = analyze(spark, parquet_path, domain, min_count=3, min_pmi=1.0, top_n=10)
            timings[domain] = round(time.perf_counter() - t0, 2)
            timings[f"{domain}_n_docs"] = res["n_docs"]
    finally:
        spark.stop()

    timings["total"] = round(timings["education"] + timings["showbiz"], 2)
    return timings


def main():
    print("=== Setup ===")
    scales = [1, 3]  # 30k → 90k để show scaling curve

    results = {"scales": []}
    for scale in scales:
        print(f"\n\n############### SCALE x{scale} ###############")
        py_json = materialize_full_dataset(scale)
        spark_parquet = materialize_parquet_scaled(scale)
        spark_path = str(spark_parquet.resolve())

        print(f"\n=== Python baseline (single-thread, scale x{scale}) ===")
        py_time = benchmark_python_baseline(py_json)
        print(f"  python: {py_time:.2f}s")

        scale_result = {
            "scale": scale,
            "python_single": round(py_time, 2),
            "runs": [],
        }

        for n in [1, 4, -1]:
            label = f"local[{n}]" if n > 0 else "local[*]"
            print(f"\n=== Spark {label} (scale x{scale}) ===")
            timings = benchmark_spark(spark_path, n)
            timings["label"] = label
            timings["speedup_vs_python"] = round(py_time / timings["total"], 2)
            scale_result["runs"].append(timings)
            print(f"  total={timings['total']}s  speedup={timings['speedup_vs_python']}x")

        results["scales"].append(scale_result)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[OK] saved → {OUT_FILE}")
    print("\n=== Summary ===")
    for s in results["scales"]:
        print(f"\nScale x{s['scale']}  (python {s['python_single']:.2f}s)")
        for r in s["runs"]:
            print(f"  Spark {r['label']:11s}  total={r['total']:>6.2f}s  "
                  f"speedup={r['speedup_vs_python']}x")


if __name__ == "__main__":
    main()
