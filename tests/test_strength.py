import pandas as pd
import pytest

from pipeline.strength import current_strength, pregame_strength, prev_season


def games_frame(rows):
    cols = ["game_id", "season", "game_date", "home_team_id", "away_team_id", "home_pts", "away_pts"]
    return pd.DataFrame(rows, columns=cols)


def test_prev_season():
    assert prev_season("2024-25") == "2023-24"
    assert prev_season("2000-01") == "1999-00"


def test_strength_uses_only_earlier_games():
    # Team 1 beats team 2 by 10, then 20. Last season both were even.
    g = games_frame(
        [
            ("a", "2020-21", "2021-01-01", 1, 2, 100, 100),
            ("b", "2021-22", "2021-10-20", 1, 2, 110, 100),
            ("c", "2021-22", "2021-10-22", 2, 1, 100, 120),
            ("d", "2021-22", "2021-10-24", 1, 2, 90, 100),
        ]
    )
    s = pregame_strength(g).set_index("game_id")
    # First game of the season: no games yet, blend fully toward last season (0).
    assert s.loc["b", "strength_gap"] == pytest.approx(0.0)
    # Second game: one prior game (+10 for team 1), weight 1/10.
    assert s.loc["c", "home_strength"] == pytest.approx(0.1 * -10)
    assert s.loc["c", "away_strength"] == pytest.approx(0.1 * 10)
    # Third game: two prior games, team 1 mean +15, weight 2/10. Game d's own
    # result (-10) must not leak in.
    assert s.loc["d", "home_strength"] == pytest.approx(0.2 * 15)
    assert s.loc["d", "strength_gap"] == pytest.approx(0.2 * 15 - 0.2 * -15)


def test_last_season_blend():
    g = games_frame(
        [
            ("a", "2020-21", "2021-01-01", 1, 2, 110, 100),  # team 1 was +10 last season
            ("b", "2021-22", "2021-10-20", 1, 2, 100, 100),
        ]
    )
    s = pregame_strength(g).set_index("game_id")
    assert s.loc["b", "home_strength"] == pytest.approx(10.0)
    assert s.loc["b", "strength_gap"] == pytest.approx(20.0)


def test_current_strength_counts_every_played_game():
    g = games_frame(
        [("x", "2026-27", f"2026-10-{20 + i}", 1, 2, 100 + i, 100) for i in range(12)]
    )
    cur = current_strength(g, "2026-27")
    assert cur[1] == pytest.approx(sum(range(12)) / 12)
    assert cur[2] == pytest.approx(-sum(range(12)) / 12)
