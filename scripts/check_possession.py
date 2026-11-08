"""How often does the possession guess match the NBA's own possession field?

The historical play-by-play (PlayByPlayV3) doesn't say who has the ball, so
``pipeline.features.possession_signal`` guesses it from the last made shot,
final made free throw, rebound or turnover. The live-format feed (cdn.nba.com,
the one live mode polls) has a ``possession`` team on every action. This
script fetches the live-format play-by-play for a few finished games per
season, lines the actions up by action number, and reports how often the
guess agrees, overall and late in close games.

    .venv/bin/python -m scripts.check_possession                  # 5 games per season
    .venv/bin/python -m scripts.check_possession --per-season 20

Needs network access to cdn.nba.com. Read-only: writes nothing.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.pull import sample_per_season


def nba_possession(game_id: str, home_id: int, away_id: int) -> pd.DataFrame:
    """The NBA's possession team for every action, as 1 home / 0 away / NaN."""
    from nba_api.live.nba.endpoints import playbyplay

    actions = playbyplay.PlayByPlay(game_id, timeout=20).get_dict()["game"]["actions"]
    df = pd.DataFrame(
        {
            "action_number": [a.get("actionNumber") for a in actions],
            "possession": [a.get("possession") for a in actions],
            "nba_score_home": pd.to_numeric([a.get("scoreHome") for a in actions], errors="coerce"),
        }
    )
    df["nba_home_ball"] = np.select([df["possession"] == home_id, df["possession"] == away_id], [1.0, 0.0], np.nan)
    return df


def compare(feats: pd.DataFrame, nba: pd.DataFrame) -> pd.DataFrame:
    """Guess vs NBA, by action number. ``nba_next`` is the NBA's possession on
    the following action, in case its field means "during" rather than "after"."""
    nba = nba.sort_values("action_number")
    nba["nba_next"] = nba["nba_home_ball"].shift(-1)
    return feats.merge(nba, on="action_number", how="inner")


def agreement(d: pd.DataFrame, col: str) -> float:
    s = d.dropna(subset=[col])
    return float((s["home_possession"] == s[col]).mean()) if len(s) else float("nan")


def report(d: pd.DataFrame) -> None:
    aligned = d.dropna(subset=["nba_score_home"])
    score_ok = (aligned["nba_score_home"] == aligned["home_score"]).mean() if len(aligned) else float("nan")
    print(f"\nAlignment check: home score agrees on {score_ok:.1%} of matched plays with a score")
    if score_ok < 0.95:
        print("  (low: the two feeds' action numbers may not line up, so the numbers below aren't reliable)")

    guessed = d[d["home_possession"] != 0.5]
    reg = guessed["is_ot"] == 0
    late = reg & (guessed["seconds_left"] > 0)
    segments = [
        ("all plays", np.ones(len(guessed), bool)),
        ("last 2 minutes", late & (guessed["seconds_left"] <= 120)),
        ("last 30 s", late & (guessed["seconds_left"] <= 30)),
        ("last 30 s, within 3 points", late & (guessed["seconds_left"] <= 30) & (guessed["margin"].abs() <= 3)),
    ]
    print(f"\n{'Plays where the guess names a team':36} {'plays':>7}  {'same play':>9}  {'next play':>9}")
    for label, m in segments:
        s = guessed[np.asarray(m)]
        print(f"{label:36} {len(s):7}  {agreement(s, 'nba_home_ball'):9.1%}  {agreement(s, 'nba_next'):9.1%}")
    unknown = d[(d["home_possession"] == 0.5) & d["nba_home_ball"].notna()]
    print(f"\nPlays where the guess says unknown (0.5) but the NBA names a team: {len(unknown)} of {len(d)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--per-season", type=int, default=5)
    args = parser.parse_args()

    cols = ["game_id", "season", "action_number", "seconds_left", "is_ot", "margin", "home_score", "home_possession"]
    feats = pd.read_parquet(config.FEATURES_PATH, columns=cols)
    games = pd.read_parquet(config.GAMES_PATH)
    games = games[games["game_id"].isin(set(feats["game_id"])) & games["season"].isin(config.SEASONS)]
    picks = sample_per_season(games, args.per_season)

    frames = []
    for i, g in enumerate(picks.itertuples(), 1):
        try:
            nba = nba_possession(g.game_id, int(g.home_team_id), int(g.away_team_id))
        except Exception as exc:  # missing file, timeout, unexpected shape
            print(f"{i}/{len(picks)} {g.season} {g.game_id}: no live-format play-by-play ({exc})")
            continue
        d = compare(feats[feats["game_id"] == g.game_id], nba)
        frames.append(d)
        print(f"{i}/{len(picks)} {g.season} {g.game_id}: {len(d)} plays matched")
        time.sleep(0.5)

    if not frames:
        print("No games could be compared.")
        return
    report(pd.concat(frames, ignore_index=True))


if __name__ == "__main__":
    main()
