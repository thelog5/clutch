import asyncio

import pytest

from api.live import LiveGame, LiveHub, normalize_scoreboard_game


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok"
    assert h["data_source"] == "synthetic"
    assert h["model"] == "logreg"
    assert h["games"] == 6


def test_search_by_team_and_season(client):
    r = client.get("/games", params={"team": "TOR", "season": "2025-26"}).json()
    assert r["total"] == 3
    for g in r["games"]:
        assert "TOR" in (g["home"]["abbr"], g["away"]["abbr"])
        assert g["season"] == "2025-26"
    dates = [g["date"] for g in r["games"]]
    assert dates == sorted(dates, reverse=True)


def test_search_free_text_and_paging(client):
    r = client.get("/games", params={"q": "lakers warriors"}).json()
    assert r["total"] == 1 and r["games"][0]["home"]["abbr"] == "LAL"
    page = client.get("/games", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 6 and len(page["games"]) == 2


def test_bad_params_rejected(client):
    assert client.get("/games", params={"season": "2025"}).status_code == 422
    assert client.get("/games", params={"sort": "odds"}).status_code == 422


def test_series_shape(client):
    s = client.get("/games/T0000/series").json()
    plays = s["plays"]
    assert len(plays) > 100
    assert [p["i"] for p in plays] == list(range(len(plays)))
    assert all(0 <= p["prob"] <= 1 for p in plays)
    for a, b in zip(plays, plays[1:], strict=False):
        assert b["delta"] == pytest.approx(b["prob"] - a["prob"], abs=2e-4)
        assert b["elapsed"] >= a["elapsed"] - 1e-6
    biggest = max(plays[1:], key=lambda p: abs(p["delta"]))
    assert s["biggest_swing"]["i"] == biggest["i"]
    last = plays[-1]
    assert (last["home_score"], last["away_score"]) == (s["game"]["home"]["score"], s["game"]["away"]["score"])
    # A finished game ends at the known result.
    assert last["prob"] == (1.0 if s["game"]["home_win"] else 0.0)
    # Substitutions and period markers are not shown as plays.
    assert not any(p["description"].startswith("SUB:") for p in plays)


def test_unknown_game_404(client):
    assert client.get("/games/nope").status_code == 404
    assert client.get("/games/nope/series").status_code == 404


def test_replay_stream_controls(client):
    with client.websocket_connect("/games/T0001/replay?speed=600") as ws:
        init = ws.receive_json()
        assert init["type"] == "init" and init["mode"] == "replay" and init["total"] > 100
        first = [ws.receive_json() for _ in range(5)]
        assert [m["i"] for m in first] == [0, 1, 2, 3, 4]
        assert {"description", "clock", "home_score", "away_score", "prob", "delta"} <= set(first[0])
        ws.send_json({"cmd": "speed", "speed": 60})
        msg = ws.receive_json()
        while msg["type"] != "state":
            msg = ws.receive_json()
        assert msg["speed"] == 60
        ws.send_json({"cmd": "restart"})
        msg = ws.receive_json()
        while msg["type"] != "reset":
            msg = ws.receive_json()


def test_replay_runs_to_end(client):
    with client.websocket_connect("/games/T0002/replay?speed=600") as ws:
        total = ws.receive_json()["total"]
        seen = 0
        while True:
            m = ws.receive_json()
            if m["type"] == "end":
                break
            seen += m["type"] == "play"
        assert seen == total


def test_replay_unknown_game(client):
    with client.websocket_connect("/games/nope/replay") as ws:
        assert ws.receive_json()["type"] == "error"


def test_scoreboard_drops_odds():
    g = normalize_scoreboard_game(
        {
            "gameId": "0022600100",
            "gameStatus": 2,
            "gameStatusText": "Q3 5:12",
            "period": 3,
            "gameClock": "PT05M12.00S",
            "homeTeam": {"teamId": 1, "teamTricode": "TOR", "teamCity": "Toronto", "teamName": "Raptors", "score": 70},
            "awayTeam": {"teamId": 2, "teamTricode": "BOS", "teamCity": "Boston", "teamName": "Celtics", "score": 66},
            "pbOdds": {"team": None, "odds": 1.5, "suspended": 0},
        }
    )
    assert g["status"] == "live" and g["clock"] == "5:12" and g["home"]["name"] == "Toronto Raptors"
    assert "odds" not in str(g).lower()


def test_live_hub_pushes_only_new_plays(bundle):
    from model.predict import WinProbModel

    model = WinProbModel("logreg", bundle["artifacts"])
    hub = LiveHub(None, store=None, model=model)
    info = {"id": "L1", "home": {"id": 10}, "away": {"id": 20}}
    lg = LiveGame(info, strength_gap=1.0)
    q: asyncio.Queue = asyncio.Queue()
    lg.subscribers.add(q)

    def act(n, team, kind, desc, h, a, clock="PT11M00.00S", **extra):
        return {"actionNumber": n, "clock": clock, "period": 1, "teamId": team, "actionType": kind,
                "scoreHome": str(h), "scoreAway": str(a), "description": desc, **extra}  # fmt: skip

    acts = [
        act(1, 10, "2pt", "A Layup", 2, 0, shotResult="Made"),
        act(2, 20, "3pt", "MISS B 3PT", 2, 0, shotResult="Missed"),
        act(3, 10, "rebound", "A REBOUND", 2, 0),
    ]
    hub.apply(lg, acts[:2])
    hub.apply(lg, acts)
    msgs = [q.get_nowait() for _ in range(q.qsize())]
    assert [m["type"] for m in msgs] == ["play", "play", "play"]
    assert [m["description"] for m in msgs] == ["A Layup", "MISS B 3PT", "A REBOUND"]

    # Feed correction: an earlier play changes -> full reset.
    acts[1] = act(2, 20, "3pt", "B 3PT Jump Shot", 2, 3, shotResult="Made")
    acts[2] = act(3, 10, "rebound", "A REBOUND", 2, 3)
    hub.apply(lg, acts)
    m = q.get_nowait()
    assert m["type"] == "reset" and len(m["plays"]) == 3

    acts.append(act(4, 0, "game", "Game End", 2, 3, subType="end"))
    hub.apply(lg, acts)
    assert lg.final
    assert lg.plays[-1]["prob"] == 0.0  # away team won 2-3
    kinds = [q.get_nowait()["type"] for _ in range(q.qsize())]
    assert kinds == ["reset", "status"]


def test_fake_live_games_are_not_replays(api_settings, monkeypatch):
    """Fake live games need their own IDs, or the game page would open them as finished replays."""
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setattr(api_settings, "LIVE_SOURCE", "fake")
    with TestClient(app) as c:
        games = c.get("/games/today").json()["games"]
        assert games and all(g["id"].startswith("FAKE") for g in games)
        live = games[0]
        assert live["status"] == "live" and live["replay_available"] is False
        assert c.get(f"/games/{live['id']}").json()["status"] == "live"
        with c.websocket_connect(f"/games/{live['id']}/live") as ws:
            init = ws.receive_json()
            assert init["type"] == "init" and init["mode"] == "live"
