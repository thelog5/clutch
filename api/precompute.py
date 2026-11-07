"""Precompute probability series so replay never calls the NBA site.

``python -m api.precompute`` scores every play of every game with the
production model and writes, to the API data folder:

* ``series.parquet``      every displayable play: prob + delta (sorted by game,
                          small row groups so the API reads one game cheaply)
* ``games.parquet``       one row per game: teams, score, date, biggest swing
* ``team_strength.json``  each team's current-season strength, for live games

``--seasons`` limits which games are written (the deploy bundle only needs the
last two seasons plus the current one); ``--out`` picks the folder.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

import pandas as pd

from api import settings
from api.series import to_series
from model.predict import load_meta, load_model
from pipeline import config
from pipeline.strength import current_strength

log = logging.getLogger("api.precompute")


def swing_summary(series: pd.DataFrame) -> pd.DataFrame:
    """Per game: the biggest swing play and the final probability."""
    s = series[series["i"] > 0]
    idx = s["delta"].abs().groupby(s["game_id"]).idxmax()
    best = s.loc[idx, ["game_id", "i", "delta", "description", "period", "clock_secs"]]
    best = best.rename(
        columns={
            "i": "swing_i",
            "delta": "swing_delta",
            "description": "swing_description",
            "period": "swing_period",
            "clock_secs": "swing_clock_secs",
        }
    )
    # How close the game was: share of plays with the outcome still in doubt.
    doubt = series.assign(close=series["prob"].between(0.2, 0.8)).groupby("game_id")["close"].mean()
    n = series.groupby("game_id").size()
    return best.set_index("game_id").assign(plays=n, in_doubt=doubt.round(3))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="*", default=None, help="default: every season with plays")
    parser.add_argument("--out", type=Path, default=settings.API_DATA_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    out = args.out if args.out.is_absolute() else config.ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    feats = pd.read_parquet(config.FEATURES_PATH)
    games = pd.read_parquet(config.GAMES_PATH)
    if args.seasons:
        feats = feats[feats["season"].isin(args.seasons)]

    meta = load_meta(settings.ARTIFACTS_DIR)
    model = load_model(meta["production"], str(settings.ARTIFACTS_DIR))
    log.info("scoring %d plays from %d games with %s", len(feats), feats["game_id"].nunique(), model.name)
    series = to_series(feats, model.predict_frame(feats))
    series = series.sort_values(["game_id", "i"]).reset_index(drop=True)
    series.to_parquet(out / "series.parquet", index=False, compression="zstd", row_group_size=20_000)

    index = games[games["game_id"].isin(series["game_id"].unique())].set_index("game_id")
    index = index.join(swing_summary(series)).reset_index()
    index.to_parquet(out / "games.parquet", index=False)

    strength = current_strength(games, config.CURRENT_SEASON)
    (out / "team_strength.json").write_text(
        json.dumps(
            {
                "season": config.CURRENT_SEASON,
                "as_of": str(games.loc[games["season"] == config.CURRENT_SEASON, "game_date"].max()),
                "teams": {str(k): round(v, 3) for k, v in sorted(strength.items())},
            },
            indent=2,
        )
        + "\n"
    )

    marker = config.DATA_DIR / "SYNTHETIC"
    if marker.exists():
        shutil.copy(marker, out / "SYNTHETIC")
    elif (out / "SYNTHETIC").exists():
        (out / "SYNTHETIC").unlink()

    size_mb = (out / "series.parquet").stat().st_size / 1e6
    log.info("wrote %d games / %d plays to %s (series %.1f MB)", len(index), len(series), out, size_mb)


if __name__ == "__main__":
    main()
