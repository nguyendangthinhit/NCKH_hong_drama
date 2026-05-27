"""
Spark Session Factory cho dự án.

Tạo SparkSession đã cấu hình sẵn JAVA_HOME, PYSPARK_PYTHON, log level.
Dùng để các script PySpark khác chỉ cần import và gọi `get_spark()`.

Usage:
    from data.spark.spark_session_factory import get_spark
    spark = get_spark(app_name="my-job", n_threads=4)
"""

import os
from pathlib import Path


# Cấu hình môi trường — chỉnh nếu JDK đặt ở chỗ khác
PROJECT_ROOT = Path(__file__).resolve().parents[2]
JAVA_HOME_DEFAULT = "D:/jdk/jdk-17.0.13+11"
VENV_PYTHON_DEFAULT = str(PROJECT_ROOT / ".venv-ml" / "Scripts" / "python.exe")
HADOOP_HOME_DEFAULT = "D:/hadoop"


def _setup_env(java_home: str, python_path: str) -> None:
    """Set các biến môi trường mà PySpark cần trên Windows."""
    os.environ.setdefault("JAVA_HOME", java_home)
    os.environ.setdefault("PYSPARK_PYTHON", python_path)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", python_path)
    # Hadoop binaries (winutils.exe + hadoop.dll) cho file system local trên Windows
    os.environ.setdefault("HADOOP_HOME", HADOOP_HOME_DEFAULT)
    os.environ["PATH"] = f"{HADOOP_HOME_DEFAULT}/bin;" + os.environ.get("PATH", "")
    # Force UTF-8 cho stdout/stderr — tránh UnicodeEncodeError trên cp1252
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")


def get_spark(
    app_name: str = "drama-intelligence",
    n_threads: int = 4,
    java_home: str = JAVA_HOME_DEFAULT,
    python_path: str = VENV_PYTHON_DEFAULT,
):
    """
    Trả về SparkSession local mode.

    Args:
        app_name: Tên job hiển thị trong Spark UI.
        n_threads: Số thread parallel (local[N]). Dùng -1 cho local[*].
        java_home: Đường dẫn JDK 17.
        python_path: Đường dẫn Python interpreter trong venv-ml.

    Returns:
        SparkSession đã cấu hình.
    """
    _setup_env(java_home, python_path)
    from pyspark.sql import SparkSession

    master = f"local[{n_threads}]" if n_threads > 0 else "local[*]"

    return (
        SparkSession.builder.master(master)
        .appName(app_name)
        # Bind localhost để tránh lỗi network trên Windows
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "127.0.0.1")
        # Log level WARN để output sạch
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


if __name__ == "__main__":
    # Smoke test: nếu chạy file này trực tiếp sẽ chạy hello-world
    spark = get_spark(app_name="smoke-test", n_threads=2)
    print(f"Spark version: {spark.version}")
    df = spark.createDataFrame(
        [(1, "hello"), (2, "spark"), (3, "world")], ["id", "text"]
    )
    df.show()
    spark.stop()
    print("OK")
