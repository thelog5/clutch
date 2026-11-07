"""One feature row per play: ``python -m pipeline.features``.

Features (PRD "Data and model"):

=================  ==========================================================
margin             home score minus away score, after the play
seconds_left       seconds left in regulation; in OT, seconds left in the OT
                   period
is_ot              1 if overtime
home_possession    1 if home has the ball, inferred from the last event
                   (made shot, final made free throw, rebound, turnover).
                   0.5 when unknown (start of a period, before the first
                   possession-deciding event).
strength_gap       home minus away season-to-date point differential per
                   game, using only games before this one
margin_x_time      margin / sqrt(seconds_left + 1)
=================  ==========================================================

Label: ``home_win`` = 1 if the home team won.

``build_features`` works on the canonical play schema (see
``pipeline/actions.py``), so the live API calls the exact same function on
the plays it has seen so far.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.actions import clock_to_seconds
from pipeline.strength import pregame_strength

log = logging.getLogger(__name__)

FEATURES = [
    "margin",
    "seconds_left",
    "is_ot",
    "home_possession",
    "strength_gap",
    "margin_x_time",
]

_FT_RE = r"(\d)\s+OF\s+(\d)"


def seconds_left(period: pd.Series, clock_secs: pd.Series) -> pd.Series:
    reg = config.REGULATION_PERIODS
    in_reg = period <= reg
    return pd.Series(
        np.where(in_reg, (reg - period) * config.PERIOD_SECONDS + clock_secs, clock_secs),
        index=period.index,
        dtype=float,
    )


def game_elapsed(period: pd.Series, clock_secs: pd.Series) -> pd.Series:
    """Seconds of game clock elapsed since tipoff (x axis of the chart)."""
    reg = config.REGULATION_PERIODS
    in_reg = period <= reg
    reg_elapsed = (period - 1) * config.PERIOD_SECONDS + (config.PERIOD_SECONDS - clock_secs)
    ot_elapsed = (
        reg * config.PERIOD_SECONDS
        + (period - reg - 1) * config.OT_SECONDS
        + (config.OT_SECONDS - clock_secs)
    )
    return pd.Series(np.where(in_reg, reg_elapsed, ot_elapsed), index=period.index, dtype=float)


def possession_signal(plays: pd.DataFrame) -> pd.Series:
    """Who has the ball after each play: 1 home, 0 away, NaN if this play doesn't say."""
    side_home = plays["side"].map({"h": 1.0, "v": 0.0})
    at = plays["action_type"]
    desc = plays["description"].str.upper()

    made_fg = at == "Made Shot"
    rebound = at == "Rebound"
    turnover = at == "Turnover"
    ft = at == "Free Throw"
    ft_nums = desc.str.extract(_FT_RE)
    ft_last = ft_nums[0].notna() & (ft_nums[0] == ft_nums[1])
    ft_made_last = ft & ft_last & ~desc.str.contains("MISS", regex=False)

    signal = pd.Series(np.nan, index=plays.index)
    signal = signal.mask(made_fg | turnover | ft_made_last, 1.0 - side_home)
    signal = signal.mask(rebound, side_home)
    return signal


def build_features(plays: pd.DataFrame, strength_gap: pd.Series | dict) -> pd.DataFrame:
    """Feature rows for canonical plays of one or many games.

    ``strength_gap`` maps game_id -> pregame strength gap.
    """
    df = plays.sort_values(["game_id", "period", "action_number"], kind="stable").reset_index(
        drop=True
    )
    df["period"] = df["period"].astype(int)

    by_game = df.groupby("game_id", sort=False)
    df["home_score"] = by_game["score_home"].ffill().fillna(0).astype(int)
    df["away_score"] = by_game["score_away"].ffill().fillna(0).astype(int)
    df["margin"] = df["home_score"] - df["away_score"]

    df["clock_secs"] = df["clock"].map(clock_to_seconds).astype(float)
    df["seconds_left"] = seconds_left(df["period"], df["clock_secs"])
    df["game_elapsed"] = game_elapsed(df["period"], df["clock_secs"])
    df["is_ot"] = (df["period"] > config.REGULATION_PERIODS).astype(int)

    signal = possession_signal(df)
    first_of_period = ~df.duplicated(["game_id", "period"])
    signal = signal.mask(first_of_period & signal.isna(), 0.5)
    df["home_possession"] = signal.groupby([df["game_id"], df["period"]]).ffill().fillna(0.5)

    gaps = pd.Series(strength_gap) if isinstance(strength_gap, dict) else strength_gap
    df["strength_gap"] = df["game_id"].map(gaps).astype(float).fillna(0.0)
    df["margin_x_time"] = df["margin"] / np.sqrt(df["seconds_left"] + 1.0)
    return df


def check_final_scores(features: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Games whose last play-by-play score disagrees with the box score."""
    last = features.groupby("game_id").tail(1).set_index("game_id")
    box = games.set_index("game_id").loc[last.index]
    bad = (last["home_score"] != box["home_pts"]) | (last["away_score"] != box["away_pts"])
    return pd.DataFrame(
        {
            "pbp_home": last.loc[bad, "home_score"],
            "pbp_away": last.loc[bad, "away_score"],
            "box_home": box.loc[bad, "home_pts"],
            "box_away": box.loc[bad, "away_pts"],
        }
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    games = pd.read_parquet(config.GAMES_PATH)
    plays = pd.read_parquet(config.PLAYS_PATH)

    strength = pregame_strength(games).set_index("game_id")["strength_gap"]
    feats = build_features(plays, strength)

    meta = games.set_index("game_id")[["season", "home_win"]]
    feats = feats.join(meta, on="game_id", how="inner")

    bad = check_final_scores(feats, games)
    if len(bad):
        log.warning("%d games: final pbp score != box score; dropping them", len(bad))
        feats = feats[~feats["game_id"].isin(bad.index)]

    keep = [
        "game_id",
        "season",
        "action_number",
        "period",
        "clock",
        "clock_secs",
        "game_elapsed",
        "home_score",
        "away_score",
        "side",
        "action_type",
        "description",
        *FEATURES,
        "home_win",
    ]
    feats = feats[keep].reset_index(drop=True)
    feats.to_parquet(config.FEATURES_PATH, index=False)

    counts = feats.groupby("season").agg(games=("game_id", "nunique"), plays=("game_id", "size"))
    log.info("wrote %s\n%s", config.FEATURES_PATH, counts.to_string())


if __name__ == "__main__":
    main()
