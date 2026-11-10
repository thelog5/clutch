"""The snapshot the site shows while the API wakes up (scripts/web_snapshot.py) has what the pages read."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "web" / "src" / "data" / "snapshot.json"


def load():
    return json.loads(SNAPSHOT.read_text())


def test_snapshot_has_every_part_the_site_reads():
    snap = load()
    assert set(snap) == {"saved_at", "meta", "model", "swings", "season_swings", "past"}
    assert snap["meta"]["seasons"] and snap["meta"]["teams"]
    assert snap["model"]["production"] in snap["model"]["models"]
    assert snap["past"]["games"] and snap["past"]["total"] >= len(snap["past"]["games"])


def test_saved_games_come_with_their_full_series():
    snap = load()
    saved = snap["swings"]["games"] + snap["season_swings"]["games"]
    assert snap["swings"]["games"] and snap["season_swings"]["games"]
    for s in saved:
        assert s["game"]["status"] == "final"
        assert len(s["plays"]) > 100  # a whole game, not a stub
        assert s["plays"][-1]["prob"] in (0.0, 1.0)  # snapped to the result
        assert s["biggest_swing"] and s["biggest_swing"]["i"] in {p["i"] for p in s["plays"]}


def test_season_swings_are_the_newest_season():
    snap = load()
    season = snap["season_swings"]["season"]
    assert season == snap["meta"]["seasons"][0]
    assert all(s["game"]["season"] == season for s in snap["season_swings"]["games"])
