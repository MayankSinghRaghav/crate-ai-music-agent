"""Ingest config — standalone (the pipeline is decoupled from the app)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

INGEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = INGEST_DIR.parent

load_dotenv(REPO_ROOT / ".env")
load_dotenv(INGEST_DIR / ".env", override=True)


@dataclass(frozen=True)
class IngestSettings:
    # AI providers (optional; absence -> deterministic stubs).
    # Groq is the default free tagging provider; Gemini and Claude also supported.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-large")

    # Reddit (official API via PRAW). Absence -> bundled fixtures.
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "").strip()
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "crate-discovery-engine/0.1").strip()
    subreddits: tuple[str, ...] = ("spotify", "truespotify")

    # App Store (Apple RSS — public, no key) + Google Play (google-play-scraper, no
    # key). Keyless, so they stay OFF by default for determinism; opt in via
    # LIVE_SOURCES=app_store,play_store.
    live_sources: tuple[str, ...] = tuple(
        s.strip().lower() for s in os.getenv("LIVE_SOURCES", "").split(",") if s.strip()
    )
    app_store_app_id: str = os.getenv("APP_STORE_APP_ID", "324684580")        # Spotify iOS
    app_store_country: str = os.getenv("APP_STORE_COUNTRY", "us").strip().lower()
    play_store_app_id: str = os.getenv("PLAY_STORE_APP_ID", "com.spotify.music")
    play_store_lang: str = os.getenv("PLAY_STORE_LANG", "en").strip()

    # X / Twitter (API v2 bearer), YouTube (Data API v3 key), Product Hunt (GraphQL
    # token) — these need credentials, so presence of the key enables live mode.
    x_bearer_token: str = os.getenv("X_BEARER_TOKEN", "").strip()
    x_query: str = os.getenv(
        "X_QUERY", '(spotify discovery OR "discover weekly") lang:en -is:retweet'
    )
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "").strip()
    youtube_video_ids: tuple[str, ...] = tuple(
        v.strip() for v in os.getenv("YOUTUBE_VIDEO_IDS", "").split(",") if v.strip()
    )
    product_hunt_token: str = os.getenv("PRODUCT_HUNT_TOKEN", "").strip()
    product_hunt_slug: str = os.getenv("PRODUCT_HUNT_SLUG", "spotify").strip()

    # Spotify Community — the official Khoros/Lithium support forum. Its public
    # Community API v2 allows keyless read of public boards, so (like the other
    # keyless sources) it stays OFF by default; opt in via
    # LIVE_SOURCES=spotify_community.
    spotify_community_base: str = os.getenv(
        "SPOTIFY_COMMUNITY_BASE", "https://community.spotify.com"
    ).strip().rstrip("/")
    spotify_community_query: str = os.getenv(
        "SPOTIFY_COMMUNITY_QUERY", "discover recommendation"
    ).strip()

    dedupe_threshold: float = float(os.getenv("DEDUPE_THRESHOLD", "0.92"))

    @property
    def reddit_live(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def app_store_live(self) -> bool:
        return "app_store" in self.live_sources

    @property
    def play_store_live(self) -> bool:
        return "play_store" in self.live_sources

    @property
    def x_live(self) -> bool:
        return bool(self.x_bearer_token)

    @property
    def youtube_live(self) -> bool:
        return bool(self.youtube_api_key)

    @property
    def product_hunt_live(self) -> bool:
        return bool(self.product_hunt_token)

    @property
    def spotify_community_live(self) -> bool:
        return "spotify_community" in self.live_sources

    @property
    def llm_provider(self) -> str:
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
    def tag_stub(self) -> bool:
        return self.llm_provider == "stub"

    @property
    def embed_stub(self) -> bool:
        return not self.openai_api_key

    @property
    def out_dir(self) -> Path:
        d = INGEST_DIR / "out"
        d.mkdir(exist_ok=True)
        return d

    @property
    def fixtures_dir(self) -> Path:
        return INGEST_DIR / "fixtures"


settings = IngestSettings()
