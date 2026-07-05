"""Live review classifier + core-finding summary endpoints."""
from fastapi.testclient import TestClient

from app import insights, llm
from app.main import app

client = TestClient(app)


# ------------------------------------------------------- classifier ---

def test_classify_stub_heuristic():
    # stub mode (conftest) -> deterministic heuristic, always responds
    out = insights.classify("I keep hearing the same 30 songs on shuffle even with 500 liked songs")
    assert out["frustration_type"] == "Repetitive / stuck in loop"
    assert out["segment"] == "Active library user"
    assert out["intensity"] in ("low", "medium", "high")
    assert out["job_to_be_done"]


def test_classify_paywall_and_intensity():
    out = insights.classify("As a free user I can never skip, discovery is completely impossible")
    assert out["frustration_type"] == "Paywall friction"
    assert out["segment"] == "Free-tier user"
    assert out["intensity"] == "high"  # 'never' / 'completely'


def test_classify_endpoint_and_validation():
    r = client.post("/insights/classify", json={"review": "the algorithm never understands my mood"})
    assert r.status_code == 200
    body = r.json()
    assert body["frustration_type"] and body["intensity"] in ("low", "medium", "high")
    assert client.post("/insights/classify", json={"review": "   "}).status_code == 422
    assert client.post("/insights/classify", json={"review": "x" * 1001}).status_code == 422


def test_classify_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(
        llm, "classify_review",
        lambda review: {"frustration_type": "Algorithm distrust",
                        "job_to_be_done": "Trust my recs", "segment": "Power user",
                        "intensity": "HIGH"},
    )
    out = insights.classify("recs are wrong")
    assert out["frustration_type"] == "Algorithm distrust"
    assert out["segment"] == "Power user"
    assert out["intensity"] == "high"  # normalised


# ----------------------------------------------------- core finding ---

def test_core_finding_stub():
    out = insights.core_finding()
    assert out is not None
    assert out["generated"] is False           # stub mode
    assert out["themes_analysed"] > 0
    assert out["reviews_analysed"] > 0
    assert "%" in out["summary"]               # deterministic template mentions share


def test_core_finding_uses_llm(monkeypatch):
    monkeypatch.setattr(llm, "summarize_themes", lambda themes: "Users can't find new music.")
    out = insights.core_finding()
    assert out["generated"] is True
    assert out["summary"] == "Users can't find new music."


def test_summary_endpoint_shape():
    r = client.get("/insights/summary")
    assert r.status_code == 200
    assert set(r.json()) >= {"summary", "themes_analysed", "reviews_analysed", "generated"}
