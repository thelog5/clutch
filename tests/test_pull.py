"""The sample pull picks games spread across each season, the same ones every run."""

import pandas as pd

from pipeline.pull import sample_per_season


def season_games():
    rows = []
    for season, start in [("2021-22", "2021-10-19"), ("2022-23", "2022-10-18")]:
        for i, day in enumerate(pd.date_range(start, periods=100, freq="D")):
            rows.append({"game_id": f"{season}-{i:03d}", "season": season, "game_date": day.strftime("%Y-%m-%d")})
    return pd.DataFrame(rows).sample(frac=1, random_state=0)  # shuffled, like a real games table


def test_sample_spreads_across_each_season():
    picked = sample_per_season(season_games(), 5)
    assert picked.groupby("season").size().to_dict() == {"2021-22": 5, "2022-23": 5}
    first = picked[picked["season"] == "2021-22"]["game_date"].tolist()
    assert first[0] == "2021-10-19" and first[-1] == "2022-01-26"  # first and last game of the season


def test_sample_is_stable_and_capped():
    games = season_games()
    assert sample_per_season(games, 7).equals(sample_per_season(games.sample(frac=1, random_state=1), 7))
    assert len(sample_per_season(games, 500)) == 200  # never more games than the season has
