"""
PySpark preprocessing pipeline.

Đọc raw JSON từ `data/process_education/cleaned_data_input/` và
`data/process_showbiz/input_clean_data/`, flatten cây comment (root + replies)
thành flat DataFrame, áp `is_trash` filter, ghi Parquet ra `data/spark/clean/`.

Run:
    python data/spark/pyspark_preprocessing.py \
        --inputs data/process_education/cleaned_data_input \
                 data/process_showbiz/input_clean_data \
        --output data/spark/clean
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Cho phép `from data.spark...` khi chạy script trực tiếp
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from data.spark.is_trash_rule import is_trash
from data.spark.spark_session_factory import get_spark


# ─── Schema ──────────────────────────────────────────────────────────────────

REPLY_SCHEMA = T.StructType([
    T.StructField("comment_id", T.StringType()),
    T.StructField("order", T.IntegerType()),
    T.StructField("reply_to_id", T.StringType()),
    T.StructField("text", T.StringType()),
    T.StructField("likes", T.IntegerType()),
])

COMMENT_SCHEMA = T.StructType([
    T.StructField("comment_id", T.StringType()),
    T.StructField("order", T.IntegerType()),
    T.StructField("text", T.StringType()),
    T.StructField("likes", T.IntegerType()),
    T.StructField("reply_count", T.IntegerType()),
    T.StructField("replies", T.ArrayType(REPLY_SCHEMA)),
])

POST_SCHEMA = T.StructType([
    T.StructField("id_content", T.StringType()),
    T.StructField("event_name", T.StringType()),
    T.StructField("sort_mode", T.StringType()),
    T.StructField("post_content", T.StringType()),
    T.StructField("comments", T.ArrayType(COMMENT_SCHEMA)),
])


# ─── UDF ─────────────────────────────────────────────────────────────────────

is_trash_udf = F.udf(is_trash, T.BooleanType())


# ─── Pipeline stages ─────────────────────────────────────────────────────────

def read_posts(spark: SparkSession, input_dirs: list[str]) -> DataFrame:
    """
    Đọc nhiều thư mục JSON, mỗi file = 1 post object.

    Parse JSON ở driver Python rồi `createDataFrame` để tránh lỗi
    `winutils.exe` của Hadoop FS trên Windows. Dataset nhỏ (< vài chục MB)
    nên overhead không đáng kể; production sẽ đọc từ S3/HDFS qua connector.
    """
    import json

    rows = []
    for d in input_dirs:
        for fp in sorted(Path(d).glob("*.json")):
            try:
                with fp.open(encoding="utf-8") as f:
                    obj = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [skip] {fp.name}: {e}")
                continue
            if not isinstance(obj, dict) or "id_content" not in obj:
                continue
            rows.append(obj)

    return spark.createDataFrame(rows, POST_SCHEMA).repartition(
        max(spark.sparkContext.defaultParallelism, 4)
    )


def flatten_comments(posts: DataFrame) -> DataFrame:
    """
    Explode cây comment (root + replies) thành flat DataFrame.

    Columns: id_content, event_name, comment_id, parent_comment_id,
             order, text, likes, depth.

    `depth=0` cho root comment, `depth=1` cho reply.
    """
    # Root comments
    roots = (
        posts.select(
            F.col("id_content"),
            F.col("event_name"),
            F.explode("comments").alias("c"),
        )
        .select(
            "id_content",
            "event_name",
            F.col("c.comment_id").alias("comment_id"),
            F.lit(None).cast(T.StringType()).alias("parent_comment_id"),
            F.col("c.order").alias("order"),
            F.col("c.text").alias("text"),
            F.col("c.likes").alias("likes"),
            F.lit(0).alias("depth"),
            F.col("c.replies").alias("replies"),
        )
    )

    # Replies (depth=1)
    replies = (
        roots.select(
            "id_content",
            "event_name",
            F.col("comment_id").alias("parent_comment_id"),
            F.explode_outer("replies").alias("r"),
        )
        .where(F.col("r").isNotNull())
        .select(
            "id_content",
            "event_name",
            F.col("r.comment_id").alias("comment_id"),
            F.col("parent_comment_id"),
            F.col("r.order").alias("order"),
            F.col("r.text").alias("text"),
            F.col("r.likes").alias("likes"),
            F.lit(1).alias("depth"),
        )
    )

    roots_flat = roots.drop("replies")
    return roots_flat.unionByName(replies)


def filter_trash(flat: DataFrame) -> DataFrame:
    """Loại comment rác bằng UDF rule-based."""
    return (
        flat.withColumn("is_trash", is_trash_udf(F.col("text")))
        .where(~F.col("is_trash"))
        .drop("is_trash")
    )


def run(
    spark: SparkSession,
    input_dirs: list[str],
    output_dir: str,
) -> dict:
    """Chạy full pipeline, trả về metric dict."""
    t0 = time.perf_counter()
    posts = read_posts(spark, input_dirs)
    n_posts = posts.count()

    t1 = time.perf_counter()
    flat = flatten_comments(posts).cache()
    n_flat = flat.count()

    t2 = time.perf_counter()
    clean = filter_trash(flat).cache()
    n_clean = clean.count()

    t3 = time.perf_counter()
    out_path = str(Path(output_dir).resolve())
    clean.write.mode("overwrite").parquet(out_path)
    t4 = time.perf_counter()

    flat.unpersist()
    clean.unpersist()

    return {
        "n_posts": n_posts,
        "n_comments_raw": n_flat,
        "n_comments_clean": n_clean,
        "n_trash": n_flat - n_clean,
        "trash_ratio": (n_flat - n_clean) / n_flat if n_flat else 0.0,
        "sec_read": round(t1 - t0, 2),
        "sec_flatten": round(t2 - t1, 2),
        "sec_filter": round(t3 - t2, 2),
        "sec_write": round(t4 - t3, 2),
        "sec_total": round(t4 - t0, 2),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True, help="Thư mục JSON đầu vào")
    parser.add_argument("--output", required=True, help="Thư mục Parquet đầu ra")
    parser.add_argument("--threads", type=int, default=4, help="local[N] threads")
    args = parser.parse_args()

    spark = get_spark(app_name="preprocess", n_threads=args.threads)
    spark.sparkContext.setLogLevel("WARN")

    try:
        metrics = run(spark, args.inputs, args.output)
        for k, v in metrics.items():
            print(f"  {k:20s} = {v}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
