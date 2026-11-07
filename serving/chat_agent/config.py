"""Đọc cấu hình từ biến môi trường / file .env cạnh module này."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parents[1]
load_dotenv(AGENT_DIR / ".env")


def _list(name: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, "").split(",") if v.strip()]


def _path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value) if value else default


@dataclass(frozen=True)
class Settings:
    showbiz_file: Path
    education_file: Path
    insights_file: Path
    llm_order: list[str]  # thứ tự thử provider, vd ["groq", "gemini"]
    groq_keys: list[str]
    groq_model: str
    gemini_keys: list[str]
    gemini_model: str
    llm_timeout_s: float
    agent_api_key: str  # rỗng = không kiểm tra header X-Agent-Key
    cors_origins: list[str]


def load_settings() -> Settings:
    data = REPO_ROOT / "data"
    return Settings(
        showbiz_file=_path("SHOWBIZ_FILE", data / "raw" / "showbiz.json"),
        education_file=_path("EDUCATION_FILE", data / "raw" / "education.json"),
        insights_file=_path("INSIGHTS_FILE", data / "analysis-output" / "insights.json"),
        llm_order=_list("LLM_ORDER") or ["groq", "gemini"],
        groq_keys=_list("GROQ_API_KEYS"),
        groq_model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        gemini_keys=_list("GEMINI_API_KEYS"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "6")),
        agent_api_key=os.getenv("AGENT_API_KEY", ""),
        cors_origins=_list("CORS_ORIGINS")
        or ["http://127.0.0.1:5173", "http://localhost:5173"],
    )
