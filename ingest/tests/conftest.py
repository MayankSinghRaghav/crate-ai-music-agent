"""Ingest tests run offline + deterministic — force the stub tagger regardless of
any real provider key in the developer's .env (mirrors the API test harness)."""
import os

os.environ["LLM_PROVIDER"] = "stub"
