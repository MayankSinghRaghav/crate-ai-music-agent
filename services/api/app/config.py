"""Config loader.

Single source of truth for runtime settings. Loads `.env` (repo root, then
services/api), exposes a frozen `settings` object, and logs clearly when the app
is running in deterministic *stub mode* (no API keys) so UI work never blocks on
external services.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("crate.config")

# services/api/app/config.py -> app -> services/api -> services -> <repo root>
API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]

# Load repo-root .env first, then a service-local one can override.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(API_DIR / ".env", override=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # --- AI providers (optional; absence triggers stub mode) ---
    # Groq is the default free provider (simplest key); Gemini and Claude also
    # supported. Embeddings stay free via the stub unless OPENAI_API_KEY is set.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-large")

    # --- Data layer ---
    # db_backend:    sqlite (default, zero-setup) | postgres (documented prod path)
    # vector_backend: local (default, in-process numpy) | pgvector | pinecone
    db_backend: str = os.getenv("DB_BACKEND", "sqlite").strip().lower()
    vector_backend: str = os.getenv("VECTOR_BACKEND", "local").strip().lower()
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    sqlite_path: str = os.getenv("CRATE_DB_PATH", str(API_DIR / "crate.db"))

    # --- Hosting ---
    # Comma-separated origins the deployed web app is served from (e.g.
    # https://crate.vercel.app). Localhost on any port is always allowed for dev.
    allowed_origins: tuple[str, ...] = tuple(
        o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
    )

    # --- Adoption (North Star) thresholds ---
    demo_mode: bool = _bool("DEMO_MODE", True)
    adopt_days: int = _int("ADOPT_DAYS", 4)
    adopt_weeks: int = _int("ADOPT_WEEKS", 3)
    # Engagement guardrail: when recent skip-rate exceeds this, the agent nudges
    # comfort back toward safer picks (less stretch).
    skip_guardrail: float = _float("SKIP_GUARDRAIL", 0.6)

    # --- Embeddings ---
    # Feature-based stub embedding dimensionality (genres+moods+eras+audio).
    # Real OpenAI text-embedding-3-large is 3072; the VectorStore is dim-agnostic.
    stub_embed_dim: int = _int("STUB_EMBED_DIM", 49)

    @property
    def llm_provider(self) -> str:
        """Which generative backend to use: groq | gemini | claude | stub.
        Honours an explicit LLM_PROVIDER override, else auto-prefers a free
        provider (Groq, then Gemini), then Claude, then the offline stub."""
        override = os.getenv("LLM_PROVIDER", "auto").strip().lower()
        if override == "stub":
            return "stub"
        if override == "groq" and self.groq_api_key:
            return "groq"
        if override == "gemini" and self.gemini_api_key:
            return "gemini"
        if override == "claude" and self.anthropic_api_key:
            return "claude"
        if self.groq_api_key:
            return "groq"
        if self.gemini_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "claude"
        return "stub"

    @property
    def llm_stub(self) -> bool:
        return self.llm_provider == "stub"

    @property
    def embed_stub(self) -> bool:
        return not self.openai_api_key

    @property
    def data_dir(self) -> Path:
        return REPO_ROOT / "data"


settings = Settings()


def log_startup_mode() -> None:
    """Emit a single, unmissable line about which mode we're in."""
    parts = []
    if settings.llm_provider == "groq":
        parts.append(f"LLM=groq:{settings.groq_model}")
    elif settings.llm_provider == "gemini":
        parts.append(f"LLM=gemini:{settings.gemini_model}")
    elif settings.llm_provider == "claude":
        parts.append(f"LLM=claude:{settings.claude_model}")
    else:
        parts.append("LLM=stub(templated)")
    parts.append(
        "EMBED=stub(feature-based)" if settings.embed_stub else f"EMBED=openai:{settings.embed_model}"
    )
    parts.append(f"DB={settings.db_backend}")
    parts.append(f"VECTORS={settings.vector_backend}")
    parts.append(f"DEMO_MODE={settings.demo_mode}")
    banner = " | ".join(parts)
    logger.warning("Crate config -> %s", banner)
    if settings.llm_stub or settings.embed_stub:
        logger.warning(
            "Running with STUBS (deterministic, offline). Add GROQ_API_KEY (free, "
            "console.groq.com/keys) to .env for real LLM bridges/summaries."
        )
