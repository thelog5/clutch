"""Live mode: poll tonight's games and push a new probability after each play.

One ``LiveGame`` per game being watched, shared by every viewer of that game:
it polls the live play-by-play every ``POLL_SECONDS`` while anyone is
subscribed, runs the *same* feature code as training on everything seen so
far, and pushes only the new plays. With a 5 second poll, a play reaches the
browser well within the PRD's 15 second budget (plus the CDN's own delay).

Sources
-------
``NBALiveSource``   cdn.nba.com live JSON via ``nba_api.live``
``FakeLiveSource``  replays stored games on an accelerated clock, in the live
                    feed's format, so live mode can be tested without a real
                    game (``CLUTCH_LIVE_SOURCE=fake``)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Protocol

from api import settings
from api.series import play_records, to_series
from pipeline.actions import format_clock, from_live
from pipeline.features import build_features

log = logging.getLogger("api.live")

STATUS = {1: "scheduled", 2: "live", 3: "final"}


class LiveSource(Protocol):
    name: str

    def scoreboard(self) -> list[dict]: ...

    def actions(self, game_id: str) -> list[dict]: ...


def _team(t: dict) -> dict:
    return {
        "id": int(t.get("teamId") or 0),
        "abbr": t.get("teamTricode", ""),
        "name": f"{t.get('teamCity', '')} {t.get('teamName', '')}".strip(),
        "score": int(t.get("score") or 0),
    }


def normalize_scoreboard_game(g: dict) -> dict:
    """liveData scoreboard game -> API shape. Drops the feed's odds block on purpose."""
    from pipeline.actions import clock_to_seconds

    clock = g.get("gameClock") or ""
    return {
        "id": str(g["gameId"]),
        "status": STATUS.get(int(g.get("gameStatus") or 1), "scheduled"),
        "status_text": (g.get("gameStatusText") or "").strip(),
        "period": int(g.get("period") or 0),
        "clock": format_clock(clock_to_seconds(clock)) if clock else "",
        "clock_secs": clock_to_seconds(clock) if clock else None,
        "start_time_utc": g.get("gameTimeUTC"),
        "home": _team(g.get("homeTeam") or {}),
        "away": _team(g.get("awayTeam") or {}),
    }


class NBALiveSource:
    name = "nba"

    def scoreboard(self) -> list[dict]:
        from nba_api.live.nba.endpoints import scoreboard

        data = scoreboard.ScoreBoard(timeout=10).get_dict()["scoreboard"]
        return [normalize_scoreboard_game(g) for g in data.get("games", [])]

    def actions(self, game_id: str) -> list[dict]:
        from nba_api.live.nba.endpoints import playbyplay

        return playbyplay.PlayByPlay(game_id, timeout=10).get_dict()["game"]["actions"]


class FakeLiveSource:
    """Stored games replayed as if they were on right now.

    Game k tips off ``k * stagger`` wall seconds after the server starts and
    runs at ``speed`` game seconds per wall second.
    """

    name = "fake"

    def __init__(self, store, n_games: int = 4, speed: float | None = None, stagger: float = 90.0):
        self.store = store
        self.speed = speed or float(os.environ.get("CLUTCH_FAKE_SPEED", "10"))
        self.started = time.time()
        recent = store.games.head(400)
        picks = recent.sort_values("in_doubt", ascending=False).head(n_games) if len(recent) else recent
        self.games = [(row, k * stagger) for k, (_, row) in enumerate(picks.iterrows())]
        self._actions: dict[str, list[dict]] = {}

    def _clock_elapsed(self, offset: float) -> float:
        return (time.time() - self.started - offset) * self.speed

    def _all_actions(self, row) -> list[dict]:
        gid = row["game_id"]
        if gid not in self._actions:
            plays = self.store.series(gid)["plays"]
            acts = []
            for n, p in enumerate(plays, 1):
                desc = p["description"]
                team_id = row["home_team_id"] if p["side"] == "h" else row["away_team_id"] if p["side"] == "v" else 0
                mins, secs = divmod(_clock_secs(p["clock"]), 60)
                acts.append(
                    {
                        "actionNumber": n,
                        "clock": f"PT{int(mins):02d}M{secs:05.2f}S",
                        "period": p["period"],
                        "teamId": int(team_id),
                        "actionType": _live_type(desc),
                        "shotResult": "Missed" if desc.upper().startswith("MISS") else "Made",
                        "scoreHome": str(p["home_score"]),
                        "scoreAway": str(p["away_score"]),
                        "description": desc,
                        "_elapsed": p["elapsed"],
                    }
                )
            self._actions[gid] = acts
        return self._actions[gid]

    def scoreboard(self) -> list[dict]:
        out = []
        for row, offset in self.games:
            acts = self._all_actions(row)
            shown = self._visible(acts, offset)
            last = shown[-1] if shown else None
            done = len(shown) == len(acts)
            status = "final" if done else "live" if shown else "scheduled"
            secs = _clock_secs_iso(last["clock"]) if last else None
            out.append(
                {
                    "id": row["game_id"],
                    "status": status,
                    "status_text": "Final" if done else (f"Q{last['period']} {format_clock(secs)}" if last else "Soon"),
                    "period": int(last["period"]) if last else 0,
                    "clock": format_clock(secs) if last else "",
                    "clock_secs": secs,
                    "start_time_utc": None,
                    "home": {"id": int(row["home_team_id"]), "abbr": row["home_abbr"], "name": row["home_name"],
                             "score": int(last["scoreHome"]) if last else 0},
                    "away": {"id": int(row["away_team_id"]), "abbr": row["away_abbr"], "name": row["away_name"],
                             "score": int(last["scoreAway"]) if last else 0},
                }  # fmt: skip
            )
        return out

    def _visible(self, acts: list[dict], offset: float) -> list[dict]:
        t = self._clock_elapsed(offset)
        return [a for a in acts if a["_elapsed"] <= t] if t >= 0 else []

    def actions(self, game_id: str) -> list[dict]:
        for row, offset in self.games:
            if row["game_id"] == game_id:
                acts = self._all_actions(row)
                shown = self._visible(acts, offset)
                if shown and len(shown) == len(acts):
                    last = shown[-1]
                    end = {**last, "actionNumber": last["actionNumber"] + 1, "teamId": 0,
                           "actionType": "game", "subType": "end", "description": "Game End"}  # fmt: skip
                    shown = [*shown, end]
                return shown
        return []


def _clock_secs(clock: str) -> float:
    if clock.startswith("0:"):
        return float(clock[2:])
    m, s = clock.split(":")
    return int(m) * 60 + float(s)


def _clock_secs_iso(clock: str) -> float:
    from pipeline.actions import clock_to_seconds

    return clock_to_seconds(clock)


def _live_type(desc: str) -> str:
    d = desc.upper()
    if "FREE THROW" in d:
        return "freethrow"
    if "REBOUND" in d:
        return "rebound"
    if "TURNOVER" in d:
        return "turnover"
    if "FOUL" in d:
        return "foul"
    if "TIMEOUT" in d:
        return "timeout"
    if "JUMP BALL" in d:
        return "jumpball"
    if "3PT" in d:
        return "3pt"
    return "2pt"


# -- hub -------------------------------------------------------------------
class LiveGame:
    def __init__(self, info: dict, strength_gap: float):
        self.info = info
        self.id = info["id"]
        self.home_id = info["home"]["id"]
        self.strength_gap = strength_gap
        self.plays: list[dict] = []
        self.final = False
        self.subscribers: set[asyncio.Queue] = set()
        self.task: asyncio.Task | None = None
        self.last_poll: float | None = None
        self.error: str | None = None


class LiveHub:
    def __init__(self, source: LiveSource | None, store, model):
        self.source = source
        self.store = store
        self.model = model
        self.games: dict[str, LiveGame] = {}
        self._board: list[dict] = []
        self._board_at = 0.0
        self.live_ok: bool | None = None
        self.last_error: str | None = None

    # -- scoreboard ------------------------------------------------------
    async def scoreboard(self) -> list[dict]:
        if self.source is None:
            return []
        if time.time() - self._board_at > settings.SCOREBOARD_TTL_SECONDS:
            try:
                self._board = await asyncio.to_thread(self.source.scoreboard)
                self.live_ok, self.last_error = True, None
            except Exception as exc:  # blocked IP, timeout, bad JSON
                log.warning("scoreboard fetch failed: %s", exc)
                self.live_ok, self.last_error = False, str(exc)
            self._board_at = time.time()
        return [self._with_prob(g) for g in self._board]

    def _with_prob(self, g: dict) -> dict:
        g = dict(g)
        lg = self.games.get(g["id"])
        if lg and lg.plays:
            g["prob"] = lg.plays[-1]["prob"]
        elif g["status"] in ("live", "final") and self.model is not None:
            g["prob"] = self._board_prob(g)
        else:
            g["prob"] = self._pregame_prob(g) if self.model is not None else None
        g["replay_available"] = self.store.game(g["id"]) is not None
        return g

    def gap(self, g: dict) -> float:
        s = self.store.strength
        return s.get(g["home"]["id"], 0.0) - s.get(g["away"]["id"], 0.0)

    def _board_prob(self, g: dict) -> float:
        """Rough probability from the scoreboard alone (possession unknown)."""
        period = max(1, g["period"])
        clock = g["clock_secs"] if g["clock_secs"] is not None else 0.0
        reg = period <= 4
        secs_left = (4 - period) * 720 + clock if reg else clock
        margin = g["home"]["score"] - g["away"]["score"]
        if g["status"] == "final":
            secs_left = 0.0
        return round(
            self.model.predict(
                {"margin": margin, "seconds_left": secs_left, "is_ot": int(not reg), "strength_gap": self.gap(g)}
            ),
            4,
        )

    def _pregame_prob(self, g: dict) -> float:
        return round(self.model.predict({"margin": 0, "seconds_left": 2880, "strength_gap": self.gap(g)}), 4)

    async def find(self, game_id: str) -> dict | None:
        for g in await self.scoreboard():
            if g["id"] == game_id:
                return g
        return None

    # -- subscriptions ---------------------------------------------------
    async def subscribe(self, game_id: str) -> tuple[LiveGame, asyncio.Queue] | None:
        info = await self.find(game_id)
        if info is None or self.model is None:
            return None
        lg = self.games.get(game_id)
        if lg is None:
            lg = self.games[game_id] = LiveGame(info, self.gap(info))
        q: asyncio.Queue = asyncio.Queue()
        lg.subscribers.add(q)
        if lg.task is None or lg.task.done():
            lg.task = asyncio.create_task(self._poll_loop(lg))
        return lg, q

    def unsubscribe(self, lg: LiveGame, q: asyncio.Queue) -> None:
        lg.subscribers.discard(q)

    async def _poll_loop(self, lg: LiveGame) -> None:
        try:
            while lg.subscribers and not lg.final:
                await self.poll_once(lg)
                await asyncio.sleep(settings.POLL_SECONDS)
        finally:
            lg.task = None

    async def poll_once(self, lg: LiveGame) -> None:
        try:
            actions = await asyncio.to_thread(self.source.actions, lg.id)
            lg.error = None
        except Exception as exc:
            lg.error = str(exc)
            log.warning("live pbp %s failed: %s", lg.id, exc)
            return
        lg.last_poll = time.time()
        self.apply(lg, actions)

    def apply(self, lg: LiveGame, actions: list[dict]) -> None:
        """Recompute the series from every action seen so far and push what's new."""
        if not actions:
            return
        canon = from_live(actions, lg.id, lg.home_id)
        canon = canon.dropna(subset=["period", "action_number"])
        feats = build_features(canon, {lg.id: lg.strength_gap})
        series = to_series(feats, self.model.predict_frame(feats))
        plays = play_records(series)
        ended = any(
            str(a.get("actionType", "")).lower() == "game" and str(a.get("subType", "")).lower() == "end"
            for a in actions
        )

        old = lg.plays
        same_prefix = len(plays) >= len(old) and all(
            plays[i]["description"] == old[i]["description"] for i in range(max(0, len(old) - 3), len(old))
        )
        if same_prefix:
            new = plays[len(old) :]
            lg.plays = plays
            for p in new:
                self._broadcast(lg, {"type": "play", **p})
        else:  # the feed edited or removed earlier plays: resend everything
            lg.plays = plays
            self._broadcast(lg, {"type": "reset", "plays": plays})
        if ended and not lg.final and lg.plays:
            # Game over: the last play's probability becomes the result.
            last = lg.plays[-1]
            final_row = feats.iloc[-1]  # includes the "game end" action's score
            result = 1.0 if final_row["home_score"] > final_row["away_score"] else 0.0
            before = last["prob"] - last["delta"]
            lg.plays[-1] = {**last, "prob": result, "delta": round(result - before, 4)}
            lg.final = True
            self._broadcast(lg, {"type": "reset", "plays": lg.plays})
            self._broadcast(lg, {"type": "status", "status": "final"})

    def _broadcast(self, lg: LiveGame, msg: dict) -> None:
        for q in list(lg.subscribers):
            q.put_nowait(msg)


def make_source(store) -> LiveSource | None:
    kind = settings.LIVE_SOURCE
    if kind == "off":
        return None
    if kind == "fake":
        return FakeLiveSource(store)
    return NBALiveSource()

