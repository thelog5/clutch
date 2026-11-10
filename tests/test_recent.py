"""The home page's latest-day biggest swings: which day, which games, and where they come from."""

import asyncio
from datetime import datetime

import pytest

from api.recent import ET, RecentGames


class StubSource:
    """Stands in for the NBA live feed: a scoreboard, play-by-play, and box scores by game ID."""

    def __init__(self, board=(), actions=None, boxes=None):
        self.board, self.acts, self.boxes = list(board), actions or {}, boxes or {}
        self.box_calls = 0

    def scoreboard(self):
        return self.board

    def actions(self, gid):
        return self.acts[gid]

    def boxscore(self, gid):
        self.box_calls += 1
        if gid not in self.boxes:
            raise RuntimeError("no such game")
        return self.boxes[gid]


class StubHub:
    def __init__(self, store, model, source):
        self.store, self.model, self.source = store, model, source

    async def scoreboard(self):
        return self.source.scoreboard()

    def gap(self, g):
        return 0.0


@pytest.fixture
def parts(api_settings, bundle):
    from api.live import FakeLiveSource
    from api.store import GameStore
    from model.predict import WinProbModel

    store = GameStore()
    fake = FakeLiveSource(store)
    rows = {r["game_id"]: r for _, r in store.games.iterrows()}

    def live_game(stored_id, new_id, start_utc, status="final"):
        """A stored game re-labelled as a new NBA game, with live-feed actions ending in 'game end'."""
        r = rows[stored_id]
        acts = fake._all_actions(r)
        end = {**acts[-1], "actionNumber": acts[-1]["actionNumber"] + 1, "teamId": 0,
               "actionType": "game", "subType": "end", "description": "Game End"}  # fmt: skip
        info = {
            "id": new_id, "status": status, "status_text": "Final", "period": 4, "clock": "", "clock_secs": 0.0,
            "start_time_utc": start_utc,
            "home": {"id": int(r["home_team_id"]), "abbr": r["home_abbr"], "name": r["home_name"],
                     "score": int(r["home_pts"])},
            "away": {"id": int(r["away_team_id"]), "abbr": r["away_abbr"], "name": r["away_name"],
                     "score": int(r["away_pts"])},
        }  # fmt: skip
        return info, [*acts, end]

    return store, WinProbModel("logreg", bundle["artifacts"]), live_game


def at(day: str, hour=10):
    return lambda: datetime.fromisoformat(f"{day}T{hour:02d}:00:00").replace(tzinfo=ET)


def run(recent):
    return asyncio.run(recent.day())


def picked(day):
    return day["label"], day["date"], [g["game"]["id"] for g in day["games"]]


def test_last_nights_finished_games_on_the_scoreboard(parts):
    store, model, live_game = parts
    a, acts_a = live_game("T0000", "0022600101", "2026-11-10T00:30:00Z")  # 7:30 pm ET on Nov 9
    b, acts_b = live_game("T0001", "0022600102", "2026-11-10T01:00:00Z")
    recent = RecentGames(StubHub(store, model, StubSource([a, b], {a["id"]: acts_a, b["id"]: acts_b})),
                         now=at("2026-11-10", 3))  # fmt: skip
    day = run(recent)
    assert (day["label"], day["date"], day["count"]) == ("yesterday", "2026-11-09", 2)
    swings = [abs(g["biggest_swing"]["delta"]) for g in day["games"]]
    assert swings == sorted(swings, reverse=True)
    s = recent.series("0022600101")  # kept, so the game opens as a replay
    assert s["game"]["date"] == "2026-11-09" and s["plays"][-1]["prob"] in (0.0, 1.0)


def test_todays_finished_games_are_today(parts):
    store, model, live_game = parts
    a, acts = live_game("T0002", "0022600140", "2026-11-10T17:00:00Z")  # noon ET
    day = run(RecentGames(StubHub(store, model, StubSource([a], {a["id"]: acts})), now=at("2026-11-10", 20)))
    assert picked(day) == ("today", "2026-11-10", [a["id"]])


def test_yesterday_from_replay_data_before_tonights_games(parts):
    store, model, live_game = parts
    tonight, _ = live_game("T0000", "0022600150", "2026-11-07T00:00:00Z", status="scheduled")
    day = run(RecentGames(StubHub(store, model, StubSource([tonight])), now=at("2026-11-06", 14)))
    assert picked(day) == ("yesterday", "2026-11-05", ["T0005"])


def test_yesterday_from_the_live_feed_when_replay_data_is_stale(parts):
    store, model, live_game = parts
    tonight, _ = live_game("T0000", "0022600150", "2026-11-11T00:00:00Z", status="scheduled")
    last_night, acts = live_game("T0002", "0022600149", "2026-11-10T00:30:00Z")
    two_nights_ago, _ = live_game("T0003", "0022600148", "2026-11-09T00:30:00Z")
    source = StubSource([tonight], {last_night["id"]: acts},
                        {last_night["id"]: last_night, two_nights_ago["id"]: two_nights_ago})  # fmt: skip
    day = run(RecentGames(StubHub(store, model, source), now=at("2026-11-10", 14)))
    assert picked(day) == ("yesterday", "2026-11-09", ["0022600149"])
    assert source.box_calls == 20  # looked back 20 game IDs from tonight's first


def test_latest_day_in_replay_data_when_nothing_newer(parts):
    store, model, _ = parts
    day = run(RecentGames(StubHub(store, model, StubSource()), now=at("2026-11-10")))
    assert picked(day) == ("latest", "2026-11-05", ["T0005"])


def test_api_serves_the_section_and_scored_games(client):
    day = client.get("/swings/recent").json()
    assert day["label"] == "latest" and day["games"][0]["game"]["id"] == "T0005"
    series = client.get("/games/T0001/series").json()
    client.app.state.recent._series["0022600101"] = {**series, "game": {**series["game"], "id": "0022600101"}}
    g = client.get("/games/0022600101").json()
    assert g["replay_available"] and g["id"] == "0022600101"
    assert client.get("/games/0022600101/series").status_code == 200
    assert client.get("/games/0022699999").status_code == 404  # unknown, and no live feed to look it up in
