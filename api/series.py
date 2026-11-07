"""Turn scored feature rows into the per-play series the web app draws.

Shared by ``api.precompute`` (finished games, written once) and the live hub
(recomputed every poll), so replay and live messages have the same shape:

    {i, period, clock, elapsed, home_score, away_score, side, description,
     prob, delta}

``prob`` is the home team's win probability after the play; ``delta`` is the
change from the previous displayed play.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from api.settings import HIDDEN_ACTION_TYPES
from pipeline.actions import format_clock

SERIES_COLUMNS = [
    "game_id",
    "i",
    "period",
    "clock_secs",
    "elapsed",
    "home_score",
    "away_score",
    "side",
    "action_type",
    "description",
    "prob",
    "delta",
]


def to_series(features: pd.DataFrame, probs: np.ndarray) -> pd.DataFrame:
    """Displayable plays only, with probability and change from the previous play."""
    df = features.assign(prob=probs)
    df = df[~df["action_type"].isin(HIDDEN_ACTION_TYPES) & (df["description"] != "")].copy()
    df["prob"] = df["prob"].round(4)
    df["delta"] = df.groupby("game_id")["prob"].diff().fillna(0.0).round(4)
    df["i"] = df.groupby("game_id").cumcount()
    df = df.rename(columns={"game_elapsed": "elapsed"})
    return df[SERIES_COLUMNS].reset_index(drop=True)


def play_records(series: pd.DataFrame) -> list[dict]:
    """JSON-ready play dicts for one game's series."""
    out = []
    for r in series.itertuples(index=False):
        out.append(
            {
                "i": int(r.i),
                "period": int(r.period),
                "clock": format_clock(r.clock_secs),
                "elapsed": float(r.elapsed),
                "home_score": int(r.home_score),
                "away_score": int(r.away_score),
                "side": r.side,
                "description": r.description,
                "prob": float(r.prob),
                "delta": float(r.delta),
            }
        )
    return out


def biggest_swing(plays: list[dict]) -> dict | None:
    """The play with the largest absolute change in home win probability."""
    if len(plays) < 2:
        return None
    best = max(plays[1:], key=lambda p: abs(p["delta"]))
    return best if best["delta"] != 0 else None
