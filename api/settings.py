"""API settings, all overridable with environment variables.

CLUTCH_API_DATA      folder with series.parquet, games.parquet, team_strength.json
                     (default: <data dir>/api; the deploy bundle uses api/data)
CLUTCH_ARTIFACTS     folder with the trained model (default: config.ARTIFACTS_DIR)
CLUTCH_REPORTS       folder with the test-season metrics.json (default: config.REPORTS_DIR)
CLUTCH_LIVE_SOURCE   "nba" (cdn.nba.com live feed), "fake" (replays stored games
                     as if live, for local testing), or "off"
CLUTCH_POLL_SECONDS  live feed poll interval (PRD: new probability within 15s)
CLUTCH_CORS_ORIGINS  comma-separated allowed origins for the web app (unset: any)
"""

from __future__ import annotations

import os
from pathlib import Path

from pipeline import config


def _path(env: str, default: Path) -> Path:
    raw = os.environ.get(env)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else config.ROOT / p


API_DATA_DIR = _path("CLUTCH_API_DATA", config.DATA_DIR / "api")
ARTIFACTS_DIR = _path("CLUTCH_ARTIFACTS", config.ARTIFACTS_DIR)
REPORTS_DIR = _path("CLUTCH_REPORTS", config.REPORTS_DIR)

SERIES_PATH = API_DATA_DIR / "series.parquet"
GAMES_PATH = API_DATA_DIR / "games.parquet"
STRENGTH_PATH = API_DATA_DIR / "team_strength.json"

LIVE_SOURCE = os.environ.get("CLUTCH_LIVE_SOURCE", "nba")
POLL_SECONDS = float(os.environ.get("CLUTCH_POLL_SECONDS", "5"))
SCOREBOARD_TTL_SECONDS = 15.0
# Unset or blank means any origin: the API only serves public, read-only data.
CORS_ORIGINS = [o.strip() for o in os.environ.get("CLUTCH_CORS_ORIGINS", "").split(",") if o.strip()] or ["*"]

REPLAY_SPEEDS = (1, 10, 60)
# Plays at the same game-clock second (fouls, free throws) still get a beat.
REPLAY_MIN_GAP_GAME_SECONDS = 1.5
REPLAY_MAX_GAP_WALL_SECONDS = 30.0

# Action types left out of the displayed series: substitutions don't change the
# state, and period markers aren't plays.
HIDDEN_ACTION_TYPES = {"Substitution", "period", "game", ""}


def data_source() -> str:
    return "synthetic" if (API_DATA_DIR / "SYNTHETIC").is_file() else "nba"
