"""Load feature rows and split them by season (never by row).

Plays within a game are nearly identical, so a random row split leaks answers
into the test set and inflates every number. Every split here is by season,
and ``assert_disjoint`` double-checks that no game lands on both sides.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pipeline import config
from pipeline.features import FEATURES


@dataclass
class Split:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame

    def summary(self) -> dict:
        return {
            name: {
                "seasons": sorted(df["season"].unique().tolist()),
                "games": int(df["game_id"].nunique()),
                "plays": int(len(df)),
            }
            for name, df in (("train", self.train), ("val", self.val), ("test", self.test))
        }


def load_features(path=None) -> pd.DataFrame:
    return pd.read_parquet(path or config.FEATURES_PATH)


def split_by_season(
    df: pd.DataFrame,
    train_seasons: list[str] = config.TRAIN_SEASONS,
    val_season: str = config.VAL_SEASON,
    test_season: str = config.TEST_SEASON,
) -> Split:
    if val_season in train_seasons or test_season in train_seasons or val_season == test_season:
        raise ValueError("train, val and test seasons must not overlap")
    split = Split(
        train=df[df["season"].isin(train_seasons)].reset_index(drop=True),
        val=df[df["season"] == val_season].reset_index(drop=True),
        test=df[df["season"] == test_season].reset_index(drop=True),
    )
    assert_disjoint(split)
    return split


def assert_disjoint(split: Split) -> None:
    """No game (and no season) may appear in more than one split."""
    parts = {"train": split.train, "val": split.val, "test": split.test}
    games = {k: set(v["game_id"]) for k, v in parts.items()}
    seasons = {k: set(v["season"]) for k, v in parts.items()}
    for a, b in (("train", "test"), ("train", "val"), ("val", "test")):
        if games[a] & games[b]:
            raise AssertionError(f"{len(games[a] & games[b])} games appear in both {a} and {b}")
        if seasons[a] & seasons[b]:
            raise AssertionError(f"seasons {seasons[a] & seasons[b]} appear in both {a} and {b}")


def xy(df: pd.DataFrame):
    return df[FEATURES].to_numpy(dtype="float32"), df["home_win"].to_numpy(dtype="float32")
