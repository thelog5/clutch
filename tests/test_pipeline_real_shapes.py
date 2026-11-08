"""The real-data code paths, exercised offline with frames shaped like nba_api output.

The build sandbox couldn't call stats.nba.com, so these pin down the parsing
of LeagueGameFinder and PlayByPlayV3 frames (column names from nba_api's
``expected_data``) without the network.
"""

import pandas as pd

from pipeline import pbp
from pipeline.actions import from_v3
from pipeline.games import collapse_to_games


def finder_rows():
    # LeagueGameFinder returns one row per team per game; numeric GAME_IDs can
    # arrive without their leading zeros.
    return pd.DataFrame(
        [
            {"SEASON_ID": "22025", "TEAM_ID": 1610612761, "TEAM_ABBREVIATION": "TOR", "TEAM_NAME": "Toronto Raptors",
             "GAME_ID": "0022500001", "GAME_DATE": "2025-10-21", "MATCHUP": "TOR vs. BOS", "WL": "W", "PTS": 110},
            {"SEASON_ID": "22025", "TEAM_ID": 1610612738, "TEAM_ABBREVIATION": "BOS", "TEAM_NAME": "Boston Celtics",
             "GAME_ID": "0022500001", "GAME_DATE": "2025-10-21", "MATCHUP": "BOS @ TOR", "WL": "L", "PTS": 104},
            {"SEASON_ID": "22025", "TEAM_ID": 1610612747, "TEAM_ABBREVIATION": "LAL", "TEAM_NAME": "Los Angeles Lakers",
             "GAME_ID": "0022500002", "GAME_DATE": "2025-10-22", "MATCHUP": "LAL @ GSW", "WL": "W", "PTS": 120},
            {"SEASON_ID": "22025", "TEAM_ID": 1610612744, "TEAM_ABBREVIATION": "GSW",
             "TEAM_NAME": "Golden State Warriors",
             "GAME_ID": "0022500002", "GAME_DATE": "2025-10-22", "MATCHUP": "GSW vs. LAL", "WL": "L", "PTS": 118},
            # Neutral site (Mexico City): both rows say "MIA @ WAS"; WAS is the designated home team.
            {"SEASON_ID": "22024", "TEAM_ID": 1610612748, "TEAM_ABBREVIATION": "MIA", "TEAM_NAME": "Miami Heat",
             "GAME_ID": "0022400147", "GAME_DATE": "2024-11-02", "MATCHUP": "MIA @ WAS", "WL": "W", "PTS": 118},
            {"SEASON_ID": "22024", "TEAM_ID": 1610612764, "TEAM_ABBREVIATION": "WAS",
             "TEAM_NAME": "Washington Wizards",
             "GAME_ID": "0022400147", "GAME_DATE": "2024-11-02", "MATCHUP": "MIA @ WAS", "WL": "L", "PTS": 98},
            # A game with only one side returned is dropped, not half-filled.
            {"SEASON_ID": "22025", "TEAM_ID": 1610612752, "TEAM_ABBREVIATION": "NYK", "TEAM_NAME": "New York Knicks",
             "GAME_ID": "0022500003", "GAME_DATE": "2025-10-22", "MATCHUP": "NYK vs. MIA", "WL": "W", "PTS": 99},
        ]
    )  # fmt: skip


def test_collapse_to_games_home_and_away():
    g = collapse_to_games(finder_rows(), "2025-26", "Regular Season").set_index("game_id")
    assert list(g.index) == ["0022400147", "0022500001", "0022500002"]
    neutral = g.loc["0022400147"]
    assert (neutral.home_abbr, neutral.away_abbr, neutral.home_win) == ("WAS", "MIA", 0)
    tor = g.loc["0022500001"]
    assert (tor.home_abbr, tor.away_abbr, tor.home_pts, tor.away_pts, tor.home_win) == ("TOR", "BOS", 110, 104, 1)
    gsw = g.loc["0022500002"]
    assert (gsw.home_abbr, gsw.away_abbr, gsw.home_win) == ("GSW", "LAL", 0)
    assert gsw.game_date == "2025-10-22"


def v3_rows():
    base = {"gameId": "0022500001", "personId": 0, "playerName": "", "playerNameI": "", "xLegacy": 0, "yLegacy": 0,
            "shotDistance": 0, "shotResult": "", "isFieldGoal": 0, "pointsTotal": 0, "videoAvailable": 0,
            "actionId": 0, "teamTricode": ""}  # fmt: skip
    rows = [
        (1, "PT12M00.00S", 1, 0, "", "", "", "period", "start", "Period Start"),
        (2, "PT11M41.00S", 1, 1610612761, "h", "2", "0", "Made Shot", "Layup", "Barnes 2' Driving Layup (2 PTS)"),
        # location blank on purpose: side must come from teamId
        (4, "PT11M20.00S", 1, 1610612738, "", "", "", "Missed Shot", "Jump Shot", "MISS Tatum 25' 3PT Jump Shot"),
        (5, "PT11M18.00S", 1, 1610612761, "h", "", "", "Rebound", "", "Poeltl REBOUND (Off:0 Def:1)"),
        (7, "PT11M02.00S", 1, 1610612761, "h", "", "", "Turnover", "Bad Pass", "Barnes Bad Pass Turnover (P1.T1)"),
        (8, "PT10M50.00S", 1, 1610612738, "v", "2", "1", "Free Throw", "Free Throw 1 of 2",
         "Brown Free Throw 1 of 2 (1 PTS)"),
        (9, "PT10M50.00S", 1, 1610612738, "v", "2", "2", "Free Throw", "Free Throw 2 of 2",
         "Brown Free Throw 2 of 2 (2 PTS)"),
    ]  # fmt: skip
    cols = ["actionNumber", "clock", "period", "teamId", "location", "scoreHome", "scoreAway", "actionType",
            "subType", "description"]  # fmt: skip
    return pd.DataFrame([{**base, **dict(zip(cols, r, strict=True))} for r in rows])


def test_from_v3_fills_side_from_team_id_and_scores():
    df = from_v3(v3_rows(), home_team_id=1610612761)
    assert df["side"].tolist() == ["", "h", "v", "h", "h", "v", "v"]
    assert df["game_id"].iloc[0] == "0022500001"
    assert df["score_home"].isna().tolist() == [True, False, True, True, True, False, False]


def test_combine_reads_cached_games(tmp_path, monkeypatch):
    monkeypatch.setattr(pbp.config, "RAW_PBP_DIR", tmp_path)
    v3_rows().to_parquet(tmp_path / "0022500001.parquet", index=False)
    games = pd.DataFrame({"game_id": ["0022500001", "0022500002"], "home_team_id": [1610612761, 1610612744]})
    plays = pbp.combine(games)  # second game isn't cached: skipped with a warning
    assert plays["game_id"].unique().tolist() == ["0022500001"]
    assert len(plays) == 7


def test_pull_skips_cached_games(tmp_path, monkeypatch):
    monkeypatch.setattr(pbp.config, "RAW_PBP_DIR", tmp_path)
    monkeypatch.setattr(pbp.config, "FAILED_PATH", tmp_path / "failed.txt")
    monkeypatch.setattr(pbp.config, "REQUEST_DELAY_S", 0.0)
    monkeypatch.setattr(pbp.time, "sleep", lambda s: None)
    v3_rows().to_parquet(tmp_path / "0022500001.parquet", index=False)
    fetched = []

    def fake_fetch(game_id, retries=4):
        fetched.append(game_id)
        if game_id == "0022500003":
            raise RuntimeError("blocked")
        return v3_rows().assign(gameId=game_id)

    monkeypatch.setattr(pbp, "fetch_game_pbp", fake_fetch)
    games = pd.DataFrame({"game_id": ["0022500001", "0022500002", "0022500003"]})
    pbp.pull_all(games)
    assert fetched == ["0022500002", "0022500003"]  # cached game not refetched
    assert (tmp_path / "0022500002.parquet").exists()
    assert (tmp_path / "failed.txt").read_text().split() == ["0022500003"]
