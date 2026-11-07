"""Synthetic play-by-play for development: ``python -m pipeline.synthetic``.

The build sandbox could not reach stats.nba.com, so this module simulates
whole seasons possession by possession and writes them in the exact raw
PlayByPlayV3 column layout. That lets the rest of the stack (features,
training, evaluation, API, web) be built and tested end to end.

**Nothing produced from this data is a real result.** The output directory
gets a ``SYNTHETIC`` marker file; the API reports ``data_source:
"synthetic"`` and the web app shows a banner whenever it is serving it.
Player names are replaced with ``"BOS #7"``-style labels so it can't be
mistaken for a real box score.

The simulation is deliberately simple but keeps the dynamics a win
probability model cares about: team strength, home edge, possession
alternation, offensive rebounds, free throws, overtime, and late-game
behavior (leaders milk the clock, trailing teams foul).
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import random
import shutil

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.games import GAME_COLUMNS
from pipeline.pbp import cache_path, combine
from pipeline.teams import TEAMS

log = logging.getLogger("pipeline.synthetic")

HOME_EDGE_PPP = 0.0125  # ~2.5 points per game
STRENGTH_CARRY = 0.65  # how much of last season's strength carries over
STRENGTH_SD = 3.8  # new spread each season, points per game
V3_COLUMNS = [
    "gameId", "actionNumber", "clock", "period", "teamId", "teamTricode", "personId",
    "playerName", "playerNameI", "xLegacy", "yLegacy", "shotDistance", "shotResult",
    "isFieldGoal", "scoreHome", "scoreAway", "pointsTotal", "location", "description",
    "actionType", "subType", "videoAvailable", "actionId",
]  # fmt: skip


def iso_clock(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(seconds, 60)
    return f"PT{int(m):02d}M{s:05.2f}S"


class GameSim:
    """Simulates one game and records PlayByPlayV3-shaped rows."""

    def __init__(self, rng: random.Random, game_id: str, home: dict, away: dict, s_home, s_away):
        self.rng = rng
        self.game_id = game_id
        self.team = {"h": home, "v": away}
        gap = (s_home - s_away) / 200.0
        self.edge = {"h": gap + HOME_EDGE_PPP, "v": -gap - HOME_EDGE_PPP}
        self.score = {"h": 0, "v": 0}
        self.points = {}
        self.rows: list[dict] = []
        self.n = 0

    # -- recording -------------------------------------------------------
    def player(self, side: str) -> str:
        return f"{self.team[side]['abbr']} #{self.rng.choice([0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 20, 21, 22, 23, 24, 30, 33])}"

    def emit(self, period, clock, side, action_type, desc, sub_type="", shot_result="", is_fg=0, scored=False):
        self.n += 1 + (self.rng.random() < 0.3)  # real action numbers have gaps
        team = self.team.get(side)
        self.rows.append(
            {
                "gameId": self.game_id,
                "actionNumber": self.n,
                "clock": iso_clock(clock),
                "period": period,
                "teamId": team["id"] if team else 0,
                "teamTricode": team["abbr"] if team else "",
                "personId": 0,
                "playerName": "",
                "playerNameI": "",
                "xLegacy": 0,
                "yLegacy": 0,
                "shotDistance": 0,
                "shotResult": shot_result,
                "isFieldGoal": is_fg,
                "scoreHome": str(self.score["h"]) if scored else "",
                "scoreAway": str(self.score["v"]) if scored else "",
                "pointsTotal": self.score["h"] + self.score["v"] if scored else 0,
                "location": side,
                "description": desc,
                "actionType": action_type,
                "subType": sub_type,
                "videoAvailable": 0,
                "actionId": self.n,
            }
        )

    def pts(self, who: str, add: int) -> int:
        self.points[who] = self.points.get(who, 0) + add
        return self.points[who]

    # -- game flow -------------------------------------------------------
    def play(self) -> list[dict]:
        rng = self.rng
        period = 1
        tip_winner = "h" if rng.random() < 0.5 else "v"
        while True:
            length = config.PERIOD_SECONDS if period <= config.REGULATION_PERIODS else config.OT_SECONDS
            clock = float(length)
            self.emit(period, clock, "", "period", "Period Start", sub_type="start")
            if period == 1 or period > config.REGULATION_PERIODS:
                off = "h" if rng.random() < 0.5 else "v"
                if period == 1:
                    off = tip_winner
                self.emit(period, clock, off, "Jump Ball", f"Jump Ball: Tip to {self.player(off)}", sub_type="recovered")
            else:
                loser = "v" if tip_winner == "h" else "h"
                off = loser if period in (2, 3) else tip_winner
            while clock > 0:
                clock, off = self.possession(period, clock, off)
            self.emit(period, 0.0, "", "period", "Period End", sub_type="end")
            if period >= config.REGULATION_PERIODS and self.score["h"] != self.score["v"]:
                break
            period += 1
        return self.rows

    def possession(self, period: int, clock: float, off: str) -> tuple[float, str]:
        rng = self.rng
        d = "v" if off == "h" else "h"
        late = period >= config.REGULATION_PERIODS and clock <= 120
        lead = self.score[off] - self.score[d]

        # Trailing defense fouls on purpose in the last ~45 seconds.
        if late and clock <= 45 and 1 <= lead <= 8 and rng.random() < 0.8:
            clock = max(0.0, clock - rng.uniform(1, 4))
            self.emit(period, clock, d, "Foul", f"{self.player(d)} P.FOUL", sub_type="personal")
            return clock, self.free_throws(period, clock, off, 2)

        if late and lead > 0:
            dur = rng.uniform(16, 24)
        elif late and lead < 0:
            dur = rng.uniform(4, 10)
        else:
            dur = min(24.0, max(3.0, rng.gauss(14.3, 5.0)))
        if rng.random() < 0.02:  # occasional timeout before the possession
            caller = d if late and lead > 0 else rng.choice(["h", "v"])
            self.emit(period, clock, caller, "Timeout", f"{self.team[caller]['abbr']} Timeout: Regular", sub_type="regular")

        shots = 0
        while True:
            buzzer = dur >= clock
            clock = max(0.0, clock - dur)
            edge = self.edge[off]
            r = rng.random()
            if r < 0.13 - edge * 0.5 and not buzzer:
                self.emit(period, clock, off, "Turnover", f"{self.player(off)} Bad Pass Turnover", sub_type="bad pass")
                if rng.random() < 0.15:
                    self.emit(period, clock, d, "Substitution", f"SUB: {self.player(d)} FOR {self.player(d)}")
                return clock, d
            if r < 0.21 and not buzzer:
                three = rng.random() < 0.12
                self.emit(period, clock, d, "Foul", f"{self.player(d)} S.FOUL", sub_type="shooting")
                return clock, self.free_throws(period, clock, off, 3 if three else 2)

            three = rng.random() < 0.39
            value = 3 if three else 2
            p = (0.36 if three else 0.535) + edge / 1.9
            if buzzer:
                p -= 0.12
            shooter = self.player(off)
            kind = "3PT Jump Shot" if three else rng.choice(["Driving Layup", "Pullup Jump Shot", "Dunk", "Floating Jump Shot"])
            if rng.random() < p:
                self.score[off] += value
                self.emit(
                    period, clock, off, "Made Shot",
                    f"{shooter} {kind} ({self.pts(shooter, value)} PTS)",
                    shot_result="Made", is_fg=1, scored=True,
                )  # fmt: skip
                if not buzzer and rng.random() < 0.03:
                    self.emit(period, clock, d, "Foul", f"{self.player(d)} S.FOUL", sub_type="shooting")
                    return clock, self.free_throws(period, clock, off, 1, shooter)
                return clock, d
            self.emit(period, clock, off, "Missed Shot", f"MISS {shooter} {kind}", shot_result="Missed", is_fg=1)
            if clock <= 0:
                return clock, d
            shots += 1
            if rng.random() < 0.26 and shots < 4:
                self.emit(period, clock, off, "Rebound", f"{self.player(off)} REBOUND (Off)", sub_type="offensive")
                dur = rng.uniform(2, 9)
                continue
            self.emit(period, clock, d, "Rebound", f"{self.player(d)} REBOUND (Def)", sub_type="defensive")
            return clock, d

    def free_throws(self, period: int, clock: float, off: str, n: int, shooter: str | None = None) -> str:
        rng = self.rng
        d = "v" if off == "h" else "h"
        shooter = shooter or self.player(off)
        made = False
        for i in range(1, n + 1):
            made = rng.random() < 0.78
            if made:
                self.score[off] += 1
                self.emit(
                    period, clock, off, "Free Throw",
                    f"{shooter} Free Throw {i} of {n} ({self.pts(shooter, 1)} PTS)",
                    sub_type=f"Free Throw {i} of {n}", shot_result="Made", scored=True,
                )  # fmt: skip
            else:
                self.emit(
                    period, clock, off, "Free Throw", f"MISS {shooter} Free Throw {i} of {n}",
                    sub_type=f"Free Throw {i} of {n}", shot_result="Missed",
                )  # fmt: skip
            if i == 1 and n > 1 and rng.random() < 0.2:
                self.emit(period, clock, off, "Substitution", f"SUB: {self.player(off)} FOR {self.player(off)}")
        if made:
            return d
        if rng.random() < 0.14:
            self.emit(period, clock, off, "Rebound", f"{self.player(off)} REBOUND (Off)", sub_type="offensive")
            return off
        self.emit(period, clock, d, "Rebound", f"{self.player(d)} REBOUND (Def)", sub_type="defensive")
        return d


# -- schedule ------------------------------------------------------------
def season_schedule(rng: random.Random, season: str, n_games: int, until: dt.date | None = None):
    """Matchups where every team plays about the same number of games, spread over dates."""
    ids = [t["id"] for t in TEAMS]
    pairs = [(h, a) for h in ids for a in ids if h != a]  # each team 58 games
    while len(pairs) < n_games:
        shuffled = ids[:]
        rng.shuffle(shuffled)
        pairs += [(shuffled[i], shuffled[i + 1]) for i in range(0, len(shuffled), 2)]
    rng.shuffle(pairs)
    pairs = pairs[:n_games]

    start = dt.date(int(season[:4]), 10, 21)
    end = dt.date(int(season[:4]) + 1, 4, 13)
    days = (end - start).days + 1
    per_day = max(1, int(np.ceil(n_games / days * 1.15)))
    out = []
    day = start
    while pairs and day <= end:
        busy: set[int] = set()
        rest = []
        today = 0
        for h, a in pairs:
            if today < per_day and h not in busy and a not in busy:
                out.append((day, h, a))
                busy |= {h, a}
                today += 1
            else:
                rest.append((h, a))
        pairs = rest
        day += dt.timedelta(days=1)
    if until is not None:
        out = [g for g in out if g[0] < until]
    return out


def team_strengths(rng: random.Random, seasons: list[str]) -> dict[str, dict[int, float]]:
    np_rng = np.random.default_rng(rng.randrange(2**32))
    prev = np.zeros(len(TEAMS))
    out = {}
    for season in seasons:
        s = STRENGTH_CARRY * prev + np_rng.normal(0, STRENGTH_SD, len(TEAMS))
        s -= s.mean()
        out[season] = {t["id"]: float(v) for t, v in zip(TEAMS, s, strict=True)}
        prev = s
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic NBA dataset.")
    parser.add_argument("--games-per-season", type=int, default=1230)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--today", type=str, default=dt.date.today().isoformat())
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if config.DATA_DIR.resolve() == (config.ROOT / "data").resolve():
        raise SystemExit("Refusing to write synthetic data into data/. Set CLUTCH_DATA_DIR=data/synthetic.")
    if config.RAW_DIR.exists():
        shutil.rmtree(config.RAW_DIR)
    config.RAW_PBP_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "SYNTHETIC").write_text("Generated by pipeline/synthetic.py. Not real NBA data.\n")

    rng = random.Random(args.seed)
    seasons = [config.PRIOR_SEASON, *config.SEASONS, config.CURRENT_SEASON]
    strengths = team_strengths(rng, seasons)
    by_id = {t["id"]: t for t in TEAMS}
    today = dt.date.fromisoformat(args.today)

    game_rows = []
    for season in seasons:
        until = today if season == config.CURRENT_SEASON else None
        sched = season_schedule(rng, season, args.games_per_season, until=until)
        yy = season[2:4]
        for n, (day, h, a) in enumerate(sched, 1):
            game_id = f"99{yy}{n:06d}"
            sim = GameSim(rng, game_id, by_id[h], by_id[a], strengths[season][h], strengths[season][a])
            rows = sim.play()
            if season != config.PRIOR_SEASON:
                pd.DataFrame(rows, columns=V3_COLUMNS).to_parquet(cache_path(game_id), index=False)
            hs, as_ = sim.score["h"], sim.score["v"]
            game_rows.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "season_type": "Regular Season",
                    "game_date": day.isoformat(),
                    "home_team_id": h,
                    "home_abbr": by_id[h]["abbr"],
                    "home_name": f"{by_id[h]['city']} {by_id[h]['name']}",
                    "away_team_id": a,
                    "away_abbr": by_id[a]["abbr"],
                    "away_name": f"{by_id[a]['city']} {by_id[a]['name']}",
                    "home_pts": hs,
                    "away_pts": as_,
                    "home_win": int(hs > as_),
                }
            )
        log.info("%s: %d games", season, len(sched))

    games = pd.DataFrame(game_rows)[GAME_COLUMNS]
    games.to_parquet(config.GAMES_PATH, index=False)
    modeled = games[games["season"] != config.PRIOR_SEASON]
    plays = combine(modeled)
    plays.to_parquet(config.PLAYS_PATH, index=False)
    log.info("synthetic: %d games, %d plays -> %s", len(modeled), len(plays), config.DATA_DIR)
    home_rate = modeled["home_win"].mean()
    margin_sd = (modeled["home_pts"] - modeled["away_pts"]).std()
    log.info("home win rate %.3f, final margin sd %.1f", home_rate, margin_sd)


if __name__ == "__main__":
    main()
