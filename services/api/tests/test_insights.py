"""Insights grounded-chat endpoint: guardrails, citation validation, and the
'assistant unavailable' path when no live provider is configured.

Tests run with LLM_PROVIDER=stub (see conftest), so the real Groq call is never
made — the live answer path is exercised by monkeypatching llm.answer_insights.
"""
from fastapi.testclient import TestClient

from app import insights, llm
from app.main import app

client = TestClient(app)


def test_snapshot_loads_seven_themes():
    themes = insights.load_themes()
    assert len(themes) == 7
    assert all("rank" in t for t in themes)


def test_ask_unavailable_in_stub_mode():
    # No live provider -> honest 503, never a fabricated answer.
    r = client.post("/insights/ask", json={"question": "what is the top opportunity?"})
    assert r.status_code == 503


def test_blank_question_rejected():
    assert client.post("/insights/ask", json={"question": "   "}).status_code == 422


def test_too_long_question_rejected():
    assert client.post("/insights/ask", json={"question": "x" * 501}).status_code == 422


def test_live_answer_shape_and_citations(monkeypatch):
    monkeypatch.setattr(
        llm,
        "answer_insights",
        lambda q, h, themes: {
            "answer": "Music discovery is the biggest theme.",
            "citations": [1, 999],  # 999 is not a real rank -> must be dropped
            "confidence": "high",
            "refused": False,
        },
    )
    r = client.post("/insights/ask", json={"question": "biggest opportunity?"})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"] == [1]  # invalid rank clamped out
    assert body["confidence"] == "high"
    assert body["refused"] is False


def test_grounded_answer_without_citations_downgraded(monkeypatch):
    monkeypatch.setattr(
        llm,
        "answer_insights",
        lambda q, h, themes: {"answer": "Sure.", "citations": [], "confidence": "high",
                              "refused": False},
    )
    body = client.post("/insights/ask", json={"question": "hello?"}).json()
    assert body["confidence"] == "low"  # no citations on a non-refusal


def test_refusal_passthrough(monkeypatch):
    monkeypatch.setattr(
        llm,
        "answer_insights",
        lambda q, h, themes: {"answer": "I can only answer from the themes here.",
                              "citations": [], "confidence": "low", "refused": True},
    )
    body = client.post("/insights/ask", json={"question": "weather in Paris?"}).json()
    assert body["refused"] is True
    assert body["citations"] == []


def test_history_is_capped(monkeypatch):
    seen = {}

    def _capture(q, h, themes):
        seen["turns"] = h
        return {"answer": "ok", "citations": [1], "confidence": "medium", "refused": False}

    monkeypatch.setattr(llm, "answer_insights", _capture)
    history = [{"role": "user", "content": f"q{i}"} for i in range(20)]
    client.post("/insights/ask", json={"question": "next?", "history": history})
    assert len(seen["turns"]) <= 6


def test_answer_insights_returns_none_in_stub():
    # Direct unit: the llm wrapper has no offline answer.
    assert llm.answer_insights("q", [], [{"rank": 1}]) is None
