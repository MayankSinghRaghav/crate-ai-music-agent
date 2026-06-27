"""Provider routing + Gemini JSON path (offline — httpx mocked, no key needed)."""
from app import llm
from app.config import settings


class _FakeResp:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


def test_defaults_to_stub_without_keys():
    assert settings.llm_provider == "stub"
    assert settings.llm_stub is True


def test_gemini_json_parses(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: _FakeResp('{"summary":"loves soul"}'))
    assert llm._gemini_json("sys", {"x": 1}) == {"summary": "loves soul"}


def test_gemini_json_extracts_from_surrounding_text(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: _FakeResp('here: {"bridge":"x","shared":["soul"]} ok'))
    assert llm._gemini_json("s", {})["shared"] == ["soul"]


def test_gemini_json_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("httpx.post", boom)
    assert llm._gemini_json("sys", {"x": 1}) is None


def test_gemini_json_handles_bad_json(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: _FakeResp("not json at all"))
    assert llm._gemini_json("sys", {"x": 1}) is None


class _FakeGroqResp:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._text}}]}


def test_groq_json_parses(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: _FakeGroqResp('{"bridge":"more soul","shared":["soul"]}'))
    out = llm._groq_json("sys", {"x": 1})
    assert out["bridge"] == "more soul" and out["shared"] == ["soul"]


def test_groq_json_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("429 rate limit")

    monkeypatch.setattr("httpx.post", boom)
    assert llm._groq_json("sys", {"x": 1}) is None
