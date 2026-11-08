"""Game lists from LeagueGameFinder, collapsed to one row per game.

LeagueGameFinder returns one row per team per game. ``MATCHUP`` tells the two
apart: ``"TOR vs. BOS"`` is the home side, ``"TOR @ BOS"`` the away side.
"""

from __future__ import annotations

import logging
import time

import pandas as pd

from pipeline import config

log = logging.getLogger(__name__)

GAME_COLUMNS = [
    "game_id",
    "season",
    "season_type",
    "game_date",
    "home_team_id",
    "home_abbr",
    "home_name",
    "away_team_id",
    "away_abbr",
    "away_name",
    "home_pts",
    "away_pts",
    "home_win",
]


def _cache_path(season: str, season_type: str):
    slug = season_type.lower().replace(" ", "_")
    return config.RAW_GAMES_DIR / f"{season}_{slug}.parquet"


def fetch_team_games(season: str, season_type: str = "Regular Season") -> pd.DataFrame:
    """Raw LeagueGameFinder team rows for one season, cached as Parquet."""
    path = _cache_path(season, season_type)
    # The season in progress gains games every night, so never trust its cache.
    if path.exists() and season != config.CURRENT_SEASON:
        return pd.read_parquet(path)

    from nba_api.stats.endpoints import leaguegamefinder

    log.info("LeagueGameFinder %s %s", season, season_type)
    for attempt in range(5):
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                player_or_team_abbreviation="T",
                season_nullable=season,
                season_type_nullable=season_type,
                league_id_nullable="00",
                timeout=60,
            )
            df = finder.get_data_frames()[0]
            break
        except Exception as exc:  # network errors, timeouts, JSON decode
            wait = 5 * 2**attempt
            log.warning("LeagueGameFinder failed (%s), retrying in %ss", exc, wait)
            time.sleep(wait)
    else:
        raise RuntimeError(f"LeagueGameFinder failed for {season} {season_type}")

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    time.sleep(config.REQUEST_DELAY_S)
    return df


def home_abbr(matchup: pd.Series) -> pd.Series:
    """The home team in MATCHUP: "TOR vs. BOS" -> TOR, "BOS @ TOR" -> TOR.

    Neutral-site games (Mexico City, Paris, Berlin, London, the NBA Cup
    semifinals in Las Vegas) come back as "MIA @ WAS" on *both* teams' rows;
    the team after the "@" is the designated home team.
    """
    vs = matchup.str.extract(r"^(\w+) vs\. ", expand=False)
    at = matchup.str.extract(r" @ (\w+)$", expand=False)
    return vs.fillna(at)


def collapse_to_games(team_rows: pd.DataFrame, season: str, season_type: str) -> pd.DataFrame:
    """Turn two team rows per game into one row with home and away columns."""
    rows = team_rows.copy()
    rows["GAME_ID"] = rows["GAME_ID"].astype(str)
    rows["is_home"] = rows["TEAM_ABBREVIATION"] == home_abbr(rows["MATCHUP"])

    home = rows[rows["is_home"]].set_index("GAME_ID")
    away = rows[~rows["is_home"]].set_index("GAME_ID")
    both = home.index.intersection(away.index)
    dropped = len(set(home.index) ^ set(away.index))
    if dropped:
        log.warning("%s %s: %d games missing a side, dropped", season, season_type, dropped)
    home, away = home.loc[both], away.loc[both]

    games = pd.DataFrame(
        {
            "game_id": both,
            "season": season,
            "season_type": season_type,
            "game_date": pd.to_datetime(home["GAME_DATE"]).dt.date.astype(str).values,
            "home_team_id": home["TEAM_ID"].astype(int).values,
            "home_abbr": home["TEAM_ABBREVIATION"].values,
            "home_name": home["TEAM_NAME"].values,
            "away_team_id": away["TEAM_ID"].astype(int).values,
            "away_abbr": away["TEAM_ABBREVIATION"].values,
            "away_name": away["TEAM_NAME"].values,
            "home_pts": home["PTS"].astype(int).values,
            "away_pts": away["PTS"].astype(int).values,
        }
    )
    games["home_win"] = (games["home_pts"] > games["away_pts"]).astype(int)
    return games.sort_values(["game_date", "game_id"]).reset_index(drop=True)[GAME_COLUMNS]


def build_games_table(seasons: list[str], season_types: list[str]) -> pd.DataFrame:
    frames = []
    for season in seasons:
        for season_type in season_types:
            team_rows = fetch_team_games(season, season_type)
            if team_rows.empty:
                continue
            frames.append(collapse_to_games(team_rows, season, season_type))
    return pd.concat(frames, ignore_index=True)
