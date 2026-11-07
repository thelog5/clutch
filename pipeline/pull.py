"""Entry point for the real data pull: ``python -m pipeline.pull``.

1. Game lists for every season (plus the prior season, for strength_gap).
2. PlayByPlayV3 for every game in the modeled seasons, cached per game.
3. One combined ``plays.parquet`` in canonical form.

Flags:
  --limit N        fetch at most N new games (smoke test the pull)
  --per-season N   only N games per season, spread across each season: a quick
                   real-data test run (the full pull reuses these games)
  --skip-pbp       only refresh game lists
  --seasons ...    override which seasons get play-by-play (default: the five
                   modeled seasons plus the current one, which is replay-only
                   and never used for training)
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.games import build_games_table
from pipeline.pbp import combine, pull_all

log = logging.getLogger("pipeline.pull")


def sample_per_season(games: pd.DataFrame, n: int) -> pd.DataFrame:
    """``n`` games per season, evenly spaced by date (same picks on every run)."""
    picked = []
    for _, g in games.sort_values(["game_date", "game_id"]).groupby("season", sort=False):
        idx = np.unique(np.linspace(0, len(g) - 1, num=min(n, len(g))).round().astype(int))
        picked.append(g.iloc[idx])
    return pd.concat(picked, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--per-season", type=int, default=None)
    parser.add_argument("--skip-pbp", action="store_true")
    parser.add_argument("--seasons", nargs="*", default=[*config.SEASONS, config.CURRENT_SEASON])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_seasons = [config.PRIOR_SEASON, *args.seasons]
    games = build_games_table(all_seasons, config.SEASON_TYPES)
    games.to_parquet(config.GAMES_PATH, index=False)
    log.info("games table: %d games across %s", len(games), ", ".join(all_seasons))

    if args.skip_pbp:
        return

    modeled = games[games["season"].isin(args.seasons)]
    if config.CURRENT_SEASON in args.seasons:
        # Only finished games have complete play-by-play.
        modeled = modeled[pd.to_datetime(modeled["game_date"]).dt.date < pd.Timestamp.now().date()]
    if args.per_season:
        modeled = sample_per_season(modeled, args.per_season)
        log.info("sample run: %d games per season, %d in all", args.per_season, len(modeled))
    pull_all(modeled, limit=args.limit)

    plays = combine(modeled)
    plays.to_parquet(config.PLAYS_PATH, index=False)
    if args.per_season:
        config.SAMPLE_MARKER.write_text(f"{args.per_season} games per season\n")
    elif args.limit is None:
        config.SAMPLE_MARKER.unlink(missing_ok=True)
    per_game = plays.groupby("game_id").size()
    log.info(
        "plays table: %d plays across %d games (median %d per game)",
        len(plays),
        per_game.size,
        int(per_game.median()),
    )


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    main()
