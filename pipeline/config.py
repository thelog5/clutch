"""Shared paths and season settings for the pipeline, model and API.

Every path hangs off ``DATA_DIR``. Point ``CLUTCH_DATA_DIR`` somewhere else
(for example ``data/synthetic``) to run the whole stack against a different
dataset without touching the real one.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("CLUTCH_DATA_DIR", ROOT / "data"))
if not DATA_DIR.is_absolute():
    DATA_DIR = ROOT / DATA_DIR

RAW_DIR = DATA_DIR / "raw"
RAW_PBP_DIR = RAW_DIR / "pbp"
RAW_GAMES_DIR = RAW_DIR / "games"
FAILED_PATH = RAW_DIR / "failed.txt"

GAMES_PATH = DATA_DIR / "games.parquet"
PLAYS_PATH = DATA_DIR / "plays.parquet"
FEATURES_PATH = DATA_DIR / "features.parquet"
SERIES_DIR = DATA_DIR / "series"

# Seasons with play-by-play. Split by season, never by row (PRD "Data and model").
TRAIN_SEASONS = ["2021-22", "2022-23", "2023-24"]
VAL_SEASON = "2024-25"
TEST_SEASON = "2025-26"
SEASONS = [*TRAIN_SEASONS, VAL_SEASON, TEST_SEASON]

# Game lists only (no play-by-play): gives last season's point differential for
# the early-season strength_gap blend in the first training season.
PRIOR_SEASON = "2020-21"

# Season currently being played (live mode + replay of this season's games).
CURRENT_SEASON = os.environ.get("CLUTCH_CURRENT_SEASON", "2026-27")

SEASON_TYPES = ["Regular Season"]

# Early-season strength_gap: blend in last season's differential until a team
# has this many games played (PRD risk table).
STRENGTH_BLEND_GAMES = 10

# Polite delay between stats.nba.com requests during the pull.
REQUEST_DELAY_S = float(os.environ.get("CLUTCH_REQUEST_DELAY", "0.7"))

REGULATION_PERIODS = 4
PERIOD_SECONDS = 12 * 60
OT_SECONDS = 5 * 60


def data_source() -> str:
    """'synthetic' when running on the generated dev dataset, else 'nba'."""
    marker = DATA_DIR / "SYNTHETIC"
    return "synthetic" if marker.exists() else "nba"
