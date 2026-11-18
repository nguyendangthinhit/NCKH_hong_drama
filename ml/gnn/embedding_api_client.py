"""
Client embedding qua HTTP API, có cache SQLite, batch, retry, xoay khoá.

Mặc định Gemini (`gemini-embedding-001`). Đổi model/số chiều: chỉ đổi
`EmbeddingConfig` (CLI của extract_api_embeddings.py nhận --model/--dim).
Cache theo (model, dim, text) nên chạy lại hoặc bị ngắt giữa chừng không tốn
lại quota.

Khoá: biến môi trường GEMINI_API_KEYS (nhiều khoá cách nhau dấu phẩy) hoặc
file .env (mặc định serving/chat_agent/.env). Không in khoá ra log.
"""

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests

DEFAULT_ENV_FILE = Path("serving/chat_agent/.env")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class EmbeddingConfig:
    model: str = "gemini-embedding-001"
    dim: int = 768
    task_type: str = "CLASSIFICATION"
    batch_size: int = 50           # tối đa API là 100; free tier ~100 văn bản/phút
    max_chars: int = 2000          # cắt văn bản quá dài
    timeout_s: float = 60.0
    max_retries: int = 90
    min_interval_s: float = 0.0    # nghỉ giữa 2 request (giảm 429 ở free tier)


def load_api_keys(env_file: Path = DEFAULT_ENV_FILE) -> list:
    raw = os.environ.get("GEMINI_API_KEYS", "")
    if not raw and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEYS="):
                raw = line.split("=", 1)[1]
                break
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise RuntimeError("Thiếu GEMINI_API_KEYS (biến môi trường hoặc " + str(env_file) + ")")
    return keys


class EmbeddingCache:
    """Cache vector float32 theo hash (model|dim|text) trong SQLite."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS emb (k TEXT PRIMARY KEY, v BLOB)")

    @staticmethod
    def key(cfg: EmbeddingConfig, text: str) -> str:
        return hashlib.sha1(f"{cfg.model}|{cfg.dim}|{text}".encode("utf-8")).hexdigest()

    def get_many(self, keys):
        found = {}
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            q = ",".join("?" * len(chunk))
            for k, v in self.db.execute(f"SELECT k, v FROM emb WHERE k IN ({q})", chunk):
                found[k] = np.frombuffer(v, dtype=np.float32)
        return found

    def put_many(self, items):
        self.db.executemany("INSERT OR REPLACE INTO emb VALUES (?, ?)",
                            [(k, v.astype(np.float32).tobytes()) for k, v in items])
        self.db.commit()


class EmbeddingClient:
    def __init__(self, cfg: EmbeddingConfig, keys: list, cache: EmbeddingCache):
        self.cfg, self.keys, self.cache = cfg, keys, cache
        self._ki = 0
        self.api_calls = 0

    def _post_batch(self, texts):
        cfg = self.cfg
        url = f"{API_ROOT}/models/{cfg.model}:batchEmbedContents"
        body = {"requests": [{
            "model": f"models/{cfg.model}",
            "content": {"parts": [{"text": t}]},
            "taskType": cfg.task_type,
            "outputDimensionality": cfg.dim,
        } for t in texts]}
        last = None
        for attempt in range(cfg.max_retries):
            key = self.keys[self._ki % len(self.keys)]
            try:
                r = requests.post(url, json=body, headers={"x-goog-api-key": key},
                                  timeout=cfg.timeout_s)
            except requests.RequestException as e:
                last = f"network: {type(e).__name__}"
                time.sleep(min(2 ** attempt, 30))
                continue
            self.api_calls += 1
            if r.status_code == 200:
                vecs = [e["values"] for e in r.json()["embeddings"]]
                if len(vecs) != len(texts):
                    raise RuntimeError("API trả sai số vector")
                return np.asarray(vecs, dtype=np.float32)
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code == 429:
                # vượt hạn mức theo phút: xoay khoá (nếu có nhiều) rồi chờ cửa sổ mới
                self._ki += 1
                wait = 65 if len(self.keys) == 1 or self._ki % len(self.keys) == 0 else 2
                print(f"  429 hạn mức, chờ {wait}s (lần {attempt + 1}/{cfg.max_retries})")
                time.sleep(wait)
                continue
            if r.status_code in (403, 401, 503, 500):
                self._ki += 1
                time.sleep(min(2 ** attempt, 30))
                continue
            break  # lỗi 4xx khác: không retry
        raise RuntimeError(f"Embedding API thất bại: {last}")

    def embed(self, texts, progress=True):
        """Trả mảng [N, dim] float32, giữ đúng thứ tự `texts`."""
        cfg = self.cfg
        clean = [(t or "").strip()[:cfg.max_chars] or "." for t in texts]
        keys = [self.cache.key(cfg, t) for t in clean]
        have = self.cache.get_many(list(set(keys)))
        todo = [i for i, k in enumerate(keys) if k not in have]
        # bỏ trùng nội dung trong cùng đợt
        uniq = {}
        for i in todo:
            uniq.setdefault(keys[i], clean[i])
        pending = list(uniq.items())
        for s in range(0, len(pending), cfg.batch_size):
            part = pending[s:s + cfg.batch_size]
            vecs = self._post_batch([t for _, t in part])
            self.cache.put_many([(k, v) for (k, _), v in zip(part, vecs)])
            for (k, _), v in zip(part, vecs):
                have[k] = v
            if progress:
                print(f"  embedded {min(s + cfg.batch_size, len(pending))}/{len(pending)} (mới)")
            if cfg.min_interval_s:
                time.sleep(cfg.min_interval_s)
        return np.stack([have[k] for k in keys]).astype(np.float32)
