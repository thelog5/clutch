"""Read-only access to precomputed games and series.

The games index (a few thousand rows) lives in memory. Series are read one
game at a time from ``series.parquet`` with a row-group filter, then cached,
so memory stays small enough for a free-tier server.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache

import pandas as pd
import pyarrow.parquet as pq

from api import settings
from api.series import biggest_swing, play_records


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


class GameStore:
    def __init__(self):
        self.games = pd.DataFrame()
        self.strength: dict[int, float] = {}
        self.reload()

    def reload(self) -> None:
        if settings.GAMES_PATH.exists():
            g = pd.read_parquet(settings.GAMES_PATH)
            self.games = g.sort_values(["game_date", "game_id"], ascending=False).reset_index(drop=True)
            self._by_id = self.games.set_index("game_id", drop=False)
        else:
            self.games = pd.DataFrame()
            self._by_id = pd.DataFrame()
        if settings.STRENGTH_PATH.exists():
            raw = json.loads(settings.STRENGTH_PATH.read_text())
            self.strength = {int(k): float(v) for k, v in raw["teams"].items()}
        self._series.cache_clear()

    @property
    def ready(self) -> bool:
        return not self.games.empty

    # -- games -----------------------------------------------------------
    def summary(self, row) -> dict:
        r = {k: _clean(v) for k, v in row.items()}
        return {
            "id": r["game_id"],
            "season": r["season"],
            "date": r["game_date"],
            "status": "final",
            "home": {"id": r["home_team_id"], "abbr": r["home_abbr"], "name": r["home_name"], "score": r["home_pts"]},
            "away": {"id": r["away_team_id"], "abbr": r["away_abbr"], "name": r["away_name"], "score": r["away_pts"]},
            "home_win": bool(r["home_win"]),
            "biggest_swing": None
            if r.get("swing_delta") is None
            else {"delta": r["swing_delta"], "description": r["swing_description"], "period": r["swing_period"]},
            "in_doubt": r.get("in_doubt"),
        }

    def game(self, game_id: str) -> dict | None:
        if not self.ready or game_id not in self._by_id.index:
            return None
        return self.summary(self._by_id.loc[game_id])

    def seasons(self) -> list[str]:
        return sorted(self.games["season"].unique().tolist(), reverse=True) if self.ready else []

    def teams(self) -> list[dict]:
        if not self.ready:
            return []
        h = self.games[["home_team_id", "home_abbr", "home_name"]].set_axis(["id", "abbr", "name"], axis=1)
        a = self.games[["away_team_id", "away_abbr", "away_name"]].set_axis(["id", "abbr", "name"], axis=1)
        t = pd.concat([h, a]).drop_duplicates("abbr").sort_values("abbr")
        return [{k: _clean(v) for k, v in r.items()} for r in t.to_dict(orient="records")]

    def search(
        self,
        team: str | None = None,
        season: str | None = None,
        q: str | None = None,
        date: str | None = None,
        sort: str = "date",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[dict]]:
        if not self.ready:
            return 0, []
        g = self.games
        if season:
            g = g[g["season"] == season]
        if team:
            t = team.upper()
            g = g[(g["home_abbr"] == t) | (g["away_abbr"] == t)]
        if date:
            g = g[g["game_date"] == date]
        if q:
            ql = q.lower().strip()
            hay = (
                g["home_abbr"] + " " + g["home_name"] + " " + g["away_abbr"] + " " + g["away_name"] + " " + g["game_date"]
            ).str.lower()
            for word in ql.split():
                g = g[hay.loc[g.index].str.contains(word, regex=False)]
        if sort == "swing":
            g = g.reindex(g["swing_delta"].abs().sort_values(ascending=False).index)
        elif sort == "close":
            g = g.sort_values("in_doubt", ascending=False)
        total = len(g)
        page = g.iloc[offset : offset + limit]
        return total, [self.summary(r) for _, r in page.iterrows()]

    # -- series ----------------------------------------------------------
    @lru_cache(maxsize=256)  # noqa: B019 - one store per process
    def _series(self, game_id: str) -> tuple:
        table = pq.read_table(settings.SERIES_PATH, filters=[("game_id", "==", game_id)])
        df = table.to_pandas().sort_values("i")
        return tuple(play_records(df))

    def series(self, game_id: str) -> dict | None:
        game = self.game(game_id)
        if game is None:
            return None
        plays = list(self._series(game_id))
        return {"game": game, "plays": plays, "biggest_swing": biggest_swing(plays)}
