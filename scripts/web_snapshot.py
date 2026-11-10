"""Save what the home page shows first into the site's bundle: web/src/data/snapshot.json.

    .venv/bin/python -m scripts.web_snapshot      (or: make snapshot)

The free API sleeps when idle and takes up to a minute to wake. The site shows
this snapshot right away (the latest day's biggest swings, this season's
biggest swings, the first page of past games, the seasons and the model's test
scores) and swaps in fresh data once the API answers. The games saved here
come with their full series, so their pages open straight away too.

Run it after `make deploy-bundle`, or whenever the biggest swings should move
on to a newer day, then commit and push: the site rebuilds with it.

It calls the API in-process on the deploy bundle (api/data), so every game it
saves is one the deployed API can open.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "src" / "data" / "snapshot.json"
PAST = "/games?sort=date&limit=10"  # the past-games table's first view (web/src/pages/HomePage.tsx)
SEASON_TOP = 3  # this season's biggest swings, shown while something loads


def build() -> dict:
    os.environ.setdefault("CLUTCH_API_DATA", "api/data")
    os.environ.setdefault("CLUTCH_ARTIFACTS", "model/artifacts")
    from fastapi.testclient import TestClient

    from api.main import app

    def get(client: TestClient, path: str) -> dict:
        res = client.get(path)
        res.raise_for_status()
        return res.json()

    with TestClient(app) as client:
        meta = get(client, "/meta")
        season = meta["seasons"][0]  # newest first
        top = get(client, f"/games?season={season}&sort=swing&limit={SEASON_TOP}")["games"]
        snap = {
            "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "meta": meta,
            "model": get(client, "/model"),
            "swings": get(client, "/swings/recent"),
            "season_swings": {"season": season, "games": [get(client, f"/games/{g['id']}/series") for g in top]},
            "past": get(client, PAST),
        }
    if not snap["swings"]["games"] or not snap["season_swings"]["games"]:
        raise SystemExit("no finished games to show; is the replay data in api/data?")
    return snap


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    snap = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snap, separators=(",", ":")) + "\n")
    swings = snap["swings"]
    names = ", ".join(f"{s['game']['away']['abbr']} at {s['game']['home']['abbr']}" for s in swings["games"])
    season = snap["season_swings"]
    top = ", ".join(f"{s['game']['away']['abbr']} at {s['game']['home']['abbr']}" for s in season["games"])
    print(f"{args.out.relative_to(ROOT)}: {args.out.stat().st_size // 1024} KB")
    print(f"  biggest swings {swings['date']}: {names}")
    print(f"  biggest swings {season['season']}: {top}")


if __name__ == "__main__":
    main()
