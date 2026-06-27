"""One-command demo: seed -> dig -> play -> simulate -> ADOPTION.

Reproduces the North Star milestone end-to-end with zero setup and no running
server (it drives the app in-process via FastAPI's TestClient).

    cd services/api
    python scripts/demo.py            # default persona: active-digger
    python scripts/demo.py genre-curious --mission jazz

Exits non-zero if no artist reaches 'adopted', so it doubles as a smoke test.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

# make the services/api dir importable regardless of where this is run from
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _ascii(s: str) -> str:
    return (s or "").encode("ascii", "ignore").decode().strip()


def _hr(title: str) -> None:
    print(f"\n{'-' * 4} {title} {'-' * (54 - len(title))}")


def run(user_id: str, mission_genre: str | None) -> int:
    _hr("seed")
    summary = client.post("/dev/seed").json()
    print(f"  catalog={summary['tracks']} tracks · users={summary['users']} · mode={summary['embed_mode']}")

    client.post(f"/dev/reset?user_id={user_id}")  # clean slate for a repeatable demo

    if mission_genre:
        _hr(f"mission: get into {mission_genre}")
        m = client.post("/missions", json={"user_id": user_id, "target_genre": mission_genre})
        if m.status_code != 200:
            print(f"  (skipped — {m.json().get('detail')})")
            mission_genre = None
        else:
            for w in m.json()["weeks"]:
                print(f"  week {w['week']}: {w['theme']} -> {[t['artist'] for t in w['tracks']]}")

    _hr("today's dig")
    dig = client.get(f"/dig?user_id={user_id}&comfort=0.4").json()
    print(f"  {_ascii(dig['greeting'])}")
    played = []
    for it in dig["items"][:3]:
        t = it["track"]
        tag = f"[{it['surface']}] " if it["surface"] != "dig" else ""
        print(f"  {tag}{t['artist']} — {t['title']}: {_ascii(it['bridge_text'])}")
        client.post("/events", json={"user_id": user_id, "track_id": t["id"], "action": "played"})
        played.append(t["artist"])
    print(f"  played: {', '.join(played)}")

    _hr("before simulation")
    m0 = client.get(f"/metrics/adoption?user_id={user_id}").json()
    print(f"  adoption rate={round(m0['adoption_rate'] * 100)}%  adopted={[a['artist'] for a in m0['adopted']]}")

    _hr("simulate 3 weeks of unprompted listening")
    res = client.post(f"/dev/simulate?user_id={user_id}&days=4&plays=1").json()
    if res.get("celebration"):
        print(f"  {_ascii(res['celebration'])}")

    _hr("after simulation")
    m1 = client.get(f"/metrics/adoption?user_id={user_id}").json()
    print(f"  adoption rate={round(m1['adoption_rate'] * 100)}%")
    print(f"  funnel: surfaced={m1['surfaced_artists']} -> tried={m1['tried_artists']} -> adopted={len(m1['adopted'])}")
    for a in m1["adopted"]:
        print(f"    [adopted] {a['artist']}  ({a['distinct_days']}d across {a['span_weeks']}w)")

    if mission_genre:
        mp = client.get(f"/missions/{user_id}").json()["progress"]
        print(f"  mission: {mp['adopted_artists']}/{mp['target_artists']} adopted ({mp['percent']}%) -> {mp['status']}")

    ok = len(m1["adopted"]) > 0
    print(f"\n{'=' * 60}\n  {'SUCCESS' if ok else 'FAILED'}: "
          f"{len(m1['adopted'])} artist(s) entered long-term rotation.\n{'=' * 60}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Crate adoption demo")
    ap.add_argument("user_id", nargs="?", default="active-digger",
                    help="persona id (default: active-digger)")
    ap.add_argument("--mission", metavar="GENRE", default=None,
                    help="also run a Discovery Mission into GENRE (e.g. jazz)")
    args = ap.parse_args()
    raise SystemExit(run(args.user_id, args.mission))
