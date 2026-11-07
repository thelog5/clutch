"""Team strength before tipoff: season-to-date point differential per game.

Only games *before* the one being predicted count, so there is no leakage of
the game's own result. Early in a season a team has few games, so for the
first ``STRENGTH_BLEND_GAMES`` games we blend toward last season's full-season
differential:

    w = min(games_played, 10) / 10
    strength = w * season_to_date + (1 - w) * last_season

A team with no last-season data (shouldn't happen after the 2020-21 pull)
blends toward 0, the league average.
"""

from __future__ import annotations

import pandas as pd

from pipeline import config


def prev_season(season: str) -> str:
    """'2024-25' -> '2023-24'."""
    start = int(season[:4]) - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _team_rows(games: pd.DataFrame) -> pd.DataFrame:
    home = pd.DataFrame(
        {
            "game_id": games["game_id"],
            "season": games["season"],
            "game_date": games["game_date"],
            "team_id": games["home_team_id"],
            "diff": games["home_pts"] - games["away_pts"],
            "is_home": True,
        }
    )
    away = pd.DataFrame(
        {
            "game_id": games["game_id"],
            "season": games["season"],
            "game_date": games["game_date"],
            "team_id": games["away_team_id"],
            "diff": games["away_pts"] - games["home_pts"],
            "is_home": False,
        }
    )
    rows = pd.concat([home, away], ignore_index=True)
    return rows.sort_values(["team_id", "season", "game_date", "game_id"]).reset_index(drop=True)


def _last_season_means(rows: pd.DataFrame) -> pd.Series:
    """Full-season mean differential, indexed by (team_id, *next* season)."""
    full = rows.groupby(["team_id", "season"])["diff"].mean()
    full.index = pd.MultiIndex.from_tuples(
        [(team, _next_season(season)) for team, season in full.index], names=["team_id", "season"]
    )
    return full


def _next_season(season: str) -> str:
    start = int(season[:4]) + 1
    return f"{start}-{str(start + 1)[-2:]}"


def _blend(prior_mean: pd.Series, n_prior: pd.Series, last: pd.Series) -> pd.Series:
    w = n_prior.clip(upper=config.STRENGTH_BLEND_GAMES) / config.STRENGTH_BLEND_GAMES
    return w * prior_mean.fillna(0.0) + (1 - w) * last.fillna(0.0)


def pregame_strength(games: pd.DataFrame) -> pd.DataFrame:
    """Per game: home_strength, away_strength and strength_gap before tipoff.

    ``games`` should include the season before the first modeled season so the
    blend has a last-season value to lean on.
    """
    rows = _team_rows(games)
    grp = rows.groupby(["team_id", "season"], sort=False)["diff"]
    n_prior = grp.cumcount()
    prior_sum = grp.cumsum() - rows["diff"]
    prior_mean = prior_sum / n_prior.where(n_prior > 0)

    last = _last_season_means(rows)
    key = pd.MultiIndex.from_arrays([rows["team_id"], rows["season"]])
    last_vals = pd.Series(last.reindex(key).to_numpy(), index=rows.index)

    rows["strength"] = _blend(prior_mean, n_prior, last_vals)
    rows["games_played"] = n_prior

    home = rows[rows["is_home"]].set_index("game_id")
    away = rows[~rows["is_home"]].set_index("game_id")
    out = pd.DataFrame(
        {
            "home_strength": home["strength"],
            "away_strength": away["strength"].reindex(home.index),
        }
    )
    out["strength_gap"] = out["home_strength"] - out["away_strength"]
    return out.reset_index()


def current_strength(games: pd.DataFrame, season: str) -> dict[int, float]:
    """Strength for each team's *next* game, using every game played so far.

    Used by live mode, where tonight's game isn't in the games table yet.
    """
    rows = _team_rows(games)
    last = _last_season_means(rows)
    this = rows[rows["season"] == season]
    stats = this.groupby("team_id")["diff"].agg(["sum", "count"])

    team_ids = set(rows.loc[rows["season"].isin([season, prev_season(season)]), "team_id"])
    out: dict[int, float] = {}
    for team in team_ids:
        n = int(stats["count"].get(team, 0))
        mean = stats["sum"].get(team, 0.0) / n if n else float("nan")
        last_val = last.get((team, season), float("nan"))
        val = _blend(pd.Series([mean]), pd.Series([n]), pd.Series([last_val])).iloc[0]
        out[int(team)] = float(val)
    return out
