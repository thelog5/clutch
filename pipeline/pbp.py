"""Historical play-by-play from PlayByPlayV3, cached one Parquet file per game.

The pull is resumable: games that already have a cache file are skipped, and
games that fail are written to ``data/raw/failed.txt`` and retried on the next
run. Kill it at any point and start it again.
"""

from __future__ import annotations

import logging
import random
import time

import pandas as pd

from pipeline import config
from pipeline.actions import from_v3

log = logging.getLogger(__name__)


def cache_path(game_id: str):
    return config.RAW_PBP_DIR / f"{game_id}.parquet"


def fetch_game_pbp(game_id: str, retries: int = 4) -> pd.DataFrame:
    """Raw PlayByPlayV3 rows for one game (network call, no cache)."""
    from nba_api.stats.endpoints import playbyplayv3

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=45)
            return resp.get_data_frames()[0]
        except Exception as exc:  # timeouts, connection resets, bad JSON
            last_exc = exc
            wait = 3 * 2**attempt + random.random()
            log.warning("pbp %s attempt %d failed: %s (sleep %.0fs)", game_id, attempt + 1, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"PlayByPlayV3 failed for {game_id}") from last_exc


def pull_all(games: pd.DataFrame, limit: int | None = None) -> None:
    """Fetch and cache play-by-play for every game not already cached."""
    config.RAW_PBP_DIR.mkdir(parents=True, exist_ok=True)
    todo = [g for g in games["game_id"] if not cache_path(g).exists()]
    if limit:
        todo = todo[:limit]
    log.info("%d games cached, %d to fetch", len(games) - len(todo), len(todo))

    failed: list[str] = []
    started = time.time()
    for i, game_id in enumerate(todo, 1):
        try:
            raw = fetch_game_pbp(game_id)
            if raw.empty:
                raise RuntimeError("empty response")
            tmp = cache_path(game_id).with_suffix(".tmp")
            raw.to_parquet(tmp, index=False)
            tmp.replace(cache_path(game_id))
        except Exception as exc:
            log.error("giving up on %s: %s", game_id, exc)
            failed.append(game_id)
        if i % 25 == 0 or i == len(todo):
            rate = i / max(time.time() - started, 1e-9)
            eta_min = (len(todo) - i) / max(rate, 1e-9) / 60
            log.info("%d/%d fetched (%.1f games/s, ~%.0f min left)", i, len(todo), rate, eta_min)
        time.sleep(config.REQUEST_DELAY_S + random.random() * 0.3)

    if failed:
        config.FAILED_PATH.write_text("\n".join(failed) + "\n")
        log.warning("%d games failed; rerun `make pull` to retry them", len(failed))
    elif config.FAILED_PATH.exists():
        config.FAILED_PATH.unlink()


def combine(games: pd.DataFrame) -> pd.DataFrame:
    """Read every cached game into one canonical plays frame."""
    frames = []
    missing = 0
    home_ids = dict(zip(games["game_id"], games["home_team_id"], strict=True))
    for game_id in games["game_id"]:
        path = cache_path(game_id)
        if not path.exists():
            missing += 1
            continue
        frames.append(from_v3(pd.read_parquet(path), home_team_id=home_ids[game_id]))
    if missing:
        log.warning("%d games have no cached play-by-play and are left out", missing)
    plays = pd.concat(frames, ignore_index=True)
    return plays
