"""The latest NBA day's biggest swings: today's finished games, or yesterday's.

Where the games come from, in order:

1. The live scoreboard's finished games, if they're from today or yesterday
   (Eastern time). Before the NBA rolls the board over in the morning it still
   shows last night's games.
2. Yesterday's games in the replay data, when it's fresh enough to have them.
3. Yesterday's games from the live feed: the game IDs just before today's,
   checked one at a time (the box score has the date and the teams).
4. The latest day in the replay data.

A game that isn't in the replay data is scored from its live play-by-play
exactly the way live mode scores it, then kept, so its page opens as a normal
replay.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from api.live import live_series
from api.series import biggest_swing, play_records, snap_final
from pipeline import config

log = logging.getLogger("api.recent")

ET = ZoneInfo("America/New_York")
SHOW = 3  # games in the section
DAY_TTL = 300.0  # seconds a picked day is reused
PROBE_BACK = 20  # game IDs to look back from today's first game
PROBE_AT_ONCE = 5


def et_date(start_time_utc: str | None) -> date | None:
    if not start_time_utc:
        return None
    return datetime.fromisoformat(start_time_utc.replace("Z", "+00:00")).astimezone(ET).date()


class RecentGames:
    def __init__(self, hub, now: Callable[[], datetime] | None = None):
        self.hub = hub
        self.now = now or (lambda: datetime.now(ET))
        self._series: dict[str, dict] = {}  # finished games scored from the live feed
        self._box: dict[str, dict | None] = {}  # game ID -> box score summary (None: no such game)
        self._day: dict | None = None
        self._day_at = 0.0
        self._lock = asyncio.Lock()

    # -- lookups used by the game routes ----------------------------------
    def series(self, game_id: str) -> dict | None:
        return self._series.get(game_id)

    async def load(self, game_id: str) -> dict | None:
        """A finished game from the live feed, scored on demand (this season's IDs only)."""
        if game_id in self._series:
            return self._series[game_id]
        board = await self.hub.scoreboard()
        if not (game_id.isdigit() and board and game_id[:5] == board[0]["id"][:5]):
            return None
        info = next((g for g in board if g["id"] == game_id), None) or await self._boxscore(game_id)
        if info is None or info["status"] != "final":
            return None
        return await self._score(info)

    # -- the section --------------------------------------------------------
    async def day(self) -> dict:
        async with self._lock:
            if self._day is None or time.time() - self._day_at > DAY_TTL:
                self._day = await self._pick()
                self._day_at = time.time()
            return self._day

    async def _pick(self) -> dict:
        today = self.now().astimezone(ET).date()
        yesterday = today - timedelta(days=1)
        store, source = self.hub.store, self.hub.source

        board = await self.hub.scoreboard()
        finals = [g for g in board if g["status"] == "final"]
        if finals and self.hub.model is not None:
            day = Counter(et_date(g["start_time_utc"]) for g in finals).most_common(1)[0][0]
            if day in (today, yesterday):
                return self._result(day, today, await self._score_all(finals))

        on_day = store.games[store.games["game_date"] == yesterday.isoformat()] if store.ready else []
        if len(on_day):
            return self._result(yesterday, today, [store.series(gid) for gid in on_day["game_id"]])

        if board and source is not None and self.hub.model is not None and hasattr(source, "boxscore"):
            found = await self._probe(board, yesterday)
            if found:
                return self._result(yesterday, today, await self._score_all(found))

        if store.ready:
            latest = store.games["game_date"].max()
            ids = store.games.loc[store.games["game_date"] == latest, "game_id"]
            return self._result(date.fromisoformat(latest), today, [store.series(gid) for gid in ids])
        return {"label": None, "date": None, "games": [], "count": 0}

    def _result(self, day: date, today: date, series: list[dict | None]) -> dict:
        games = [s for s in series if s and s["plays"]]
        games.sort(key=lambda s: abs(s["biggest_swing"]["delta"]) if s["biggest_swing"] else 0, reverse=True)
        label = "today" if day == today else "yesterday" if day == today - timedelta(days=1) else "latest"
        return {"label": label, "date": day.isoformat(), "games": games[:SHOW], "count": len(games)}

    # -- live feed ------------------------------------------------------------
    async def _probe(self, board: list[dict], day: date) -> list[dict]:
        ids = sorted(int(g["id"]) for g in board if g["id"].isdigit())
        if not ids:
            return []
        sem = asyncio.Semaphore(PROBE_AT_ONCE)

        async def one(gid: str):
            async with sem:
                return await self._boxscore(gid)

        found = await asyncio.gather(*(one(f"{ids[0] - k:010d}") for k in range(1, PROBE_BACK + 1)))
        return [g for g in found if g and g["status"] == "final" and et_date(g["start_time_utc"]) == day]

    async def _boxscore(self, game_id: str) -> dict | None:
        if game_id not in self._box:
            try:
                self._box[game_id] = await asyncio.to_thread(self.hub.source.boxscore, game_id)
            except Exception as exc:  # no such game, timeout, blocked
                log.info("box score %s: %s", game_id, exc)
                self._box[game_id] = None
        return self._box[game_id]

    async def _score_all(self, games: list[dict]) -> list[dict | None]:
        sem = asyncio.Semaphore(PROBE_AT_ONCE)

        async def one(g):
            async with sem:
                return await self._score(g)

        return list(await asyncio.gather(*(one(g) for g in games)))

    async def _score(self, info: dict) -> dict | None:
        """A finished game's full series from its live play-by-play."""
        gid = info["id"]
        if gid in self._series:
            return self._series[gid]
        if self.hub.store.game(gid) is not None:
            return self.hub.store.series(gid)
        try:
            actions = await asyncio.to_thread(self.hub.source.actions, gid)
        except Exception as exc:
            log.warning("play-by-play %s: %s", gid, exc)
            return None
        if not actions:
            return None
        home_win = info["home"]["score"] > info["away"]["score"]
        _, series = live_series(actions, gid, info["home"]["id"], self.hub.gap(info), self.hub.model)
        plays = play_records(snap_final(series, {gid: float(home_win)}))
        swing = biggest_swing(plays)
        day = et_date(info.get("start_time_utc"))
        summary = {
            "id": gid,
            "season": config.CURRENT_SEASON,
            "date": day.isoformat() if day else None,
            "status": "final",
            "home": info["home"],
            "away": info["away"],
            "home_win": home_win,
            "biggest_swing": swing and {k: swing[k] for k in ("delta", "description", "period")},
            "in_doubt": None,
        }
        self._series[gid] = {"game": summary, "plays": plays, "biggest_swing": swing}
        return self._series[gid]
