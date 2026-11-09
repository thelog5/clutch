import math

import pandas as pd
import pytest

from pipeline.actions import CANONICAL_COLUMNS, clock_to_seconds, format_clock, from_live
from pipeline.features import FEATURES, build_features


def play(n, period, clock, side, action_type, desc="", home=None, away=None):
    return {
        "game_id": "G1",
        "action_number": n,
        "period": period,
        "clock": clock,
        "side": side,
        "action_type": action_type,
        "sub_type": "",
        "description": desc,
        "score_home": home,
        "score_away": away,
    }


def frame(rows):
    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)


@pytest.mark.parametrize(
    ("clock", "secs"),
    [("PT12M00.00S", 720.0), ("PT11M48.00S", 708.0), ("PT00M04.30S", 4.3), ("PT05M00S", 300.0),
     ("", 0.0), ("2:30", 150.0)],
)  # fmt: skip
def test_clock_to_seconds(clock, secs):
    assert clock_to_seconds(clock) == pytest.approx(secs)


def test_format_clock():
    assert format_clock(708) == "11:48"
    assert format_clock(4.3) == "0:04.3"


def test_seconds_left_regulation_and_ot():
    f = build_features(
        frame(
            [
                play(1, 1, "PT12M00.00S", "", "period"),
                play(2, 3, "PT06M00.00S", "", "period"),
                play(3, 4, "PT00M30.00S", "", "period"),
                play(4, 5, "PT04M00.00S", "", "period"),
            ]
        ),
        {"G1": 0.0},
    )
    assert f["seconds_left"].tolist() == [2880.0, 720 + 360.0, 30.0, 240.0]
    assert f["is_ot"].tolist() == [0, 0, 0, 1]
    assert f["game_elapsed"].tolist() == [0.0, 1800.0, 2850.0, 2940.0]


def test_scores_forward_fill_and_margin_x_time():
    f = build_features(
        frame(
            [
                play(1, 1, "PT12M00.00S", "", "period"),
                play(2, 1, "PT11M40.00S", "h", "Made Shot", "A 2pt", 2, 0),
                play(3, 1, "PT11M20.00S", "v", "Missed Shot", "MISS B"),
                play(4, 4, "PT00M00.00S", "v", "Made Shot", "B 3pt", 2, 3),
            ]
        ),
        {"G1": 1.5},
    )
    assert f["margin"].tolist() == [0, 2, 2, -1]
    assert f["strength_gap"].eq(1.5).all()
    row = f.iloc[1]
    assert row["margin_x_time"] == pytest.approx(2 / math.sqrt(row["seconds_left"] + 1))
    assert set(FEATURES) <= set(f.columns)


def test_late_logged_play_goes_by_game_clock():
    # The feed logs an instant-replay review after the period ends: a later
    # action_number, an earlier clock, and the score at that moment.
    f = build_features(
        frame(
            [
                play(1, 4, "PT03M30.00S", "h", "Made Shot", "A 2pt", 109, 106),
                play(2, 4, "", "", "Timeout", "no clock: keeps its place"),
                play(3, 4, "PT03M08.00S", "v", "Made Shot", "B 2pt", 109, 108),
                play(4, 4, "PT00M01.20S", "h", "Made Shot", "A 3pt", 119, 116),
                play(5, 4, "PT00M00.00S", "", "period", "End of 4th Period", 119, 116),
                play(6, 4, "PT03M08.00S", "", "Instant Replay", "Instant Replay", 109, 108),
            ]
        ),
        {"G1": 0.0},
    )
    assert f["action_number"].tolist() == [1, 2, 3, 6, 4, 5]
    assert (f.iloc[-1]["home_score"], f.iloc[-1]["away_score"]) == (119, 116)


def test_possession_heuristic():
    rows = [
        play(1, 1, "PT12M00.00S", "", "period", "Period Start"),
        play(2, 1, "PT11M50.00S", "h", "Made Shot", "A layup", 2, 0),  # away ball
        play(3, 1, "PT11M30.00S", "v", "Missed Shot", "MISS B"),  # unchanged
        play(4, 1, "PT11M29.00S", "h", "Rebound", "A REBOUND"),  # home ball
        play(5, 1, "PT11M10.00S", "h", "Turnover", "A Turnover"),  # away ball
        play(6, 1, "PT11M00.00S", "h", "Foul", "A S.FOUL"),  # unchanged
        play(7, 1, "PT11M00.00S", "v", "Free Throw", "B Free Throw 1 of 2", 2, 1),  # unchanged
        play(8, 1, "PT11M00.00S", "v", "Free Throw", "B Free Throw 2 of 2", 2, 2),  # home ball
        play(9, 1, "PT10M40.00S", "h", "Foul", "A foul"),
        play(10, 1, "PT10M40.00S", "v", "Free Throw", "MISS B Free Throw 2 of 2"),  # missed: unchanged
        play(11, 2, "PT12M00.00S", "", "period", "Period Start"),  # reset
    ]
    f = build_features(frame(rows), {"G1": 0.0})
    assert f["home_possession"].tolist() == [0.5, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0.5]


def test_live_actions_normalize_like_v3():
    actions = [
        {"actionNumber": 2, "clock": "PT11M40.00S", "period": 1, "teamId": 10, "actionType": "2pt",
         "shotResult": "Made", "scoreHome": "2", "scoreAway": "0", "description": "A Layup"},
        {"actionNumber": 3, "clock": "PT11M20.00S", "period": 1, "teamId": 20, "actionType": "freethrow",
         "subType": "1 of 1", "shotResult": "Missed", "scoreHome": "2", "scoreAway": "0",
         "description": "B Free Throw 1 of 1"},
        {"actionNumber": 4, "clock": "PT11M19.00S", "period": 1, "teamId": 10, "actionType": "rebound",
         "scoreHome": "2", "scoreAway": "0", "description": "A REBOUND"},
    ]  # fmt: skip
    df = from_live(actions, "G1", home_team_id=10)
    assert df["action_type"].tolist() == ["Made Shot", "Free Throw", "Rebound"]
    assert df["side"].tolist() == ["h", "v", "h"]
    assert df["description"].iloc[1].startswith("MISS")
    f = build_features(df, {"G1": 0.0})
    assert f["home_possession"].tolist() == [0, 0, 1]


def _counts(rows):
    from pipeline.features import situation_counts

    df = frame(rows)
    df["period"] = df["period"].astype(int)
    df["clock_secs"] = df["clock"].map(clock_to_seconds)
    return situation_counts(df)


def to(n, period, clock, side, sub="Regular"):
    r = play(n, period, clock, side, "Timeout", f"Timeout: {sub}")
    r["sub_type"] = sub
    return r


def foul(n, period, clock, side, sub="Personal"):
    r = play(n, period, clock, side, "Foul", f"{sub} foul")
    r["sub_type"] = sub
    return r


def test_timeouts_left_follow_nba_rules():
    rows = [to(i, 1, "PT08M00.00S", "h") for i in range(1, 4)]  # 3 in the 1st quarter: 4 left
    rows += [play(10, 4, "PT11M00.00S", "", "period")]  # 4th quarter: still 4 (cap is 4)
    rows += [to(11, 4, "PT05M00.00S", "h"), play(12, 4, "PT02M59.00S", "", "Rebound")]  # 3 left, then capped at 2
    rows += [to(13, 4, "PT01M00.00S", "h"), to(14, 4, "PT00M30.00S", "h", "Coach Challenge")]  # challenge not charged
    rows += [play(15, 5, "PT05M00.00S", "", "period")]  # overtime: 2 fresh
    c = _counts(rows)
    assert c["home_timeouts"].tolist() == [6, 5, 4, 4, 3, 2, 1, 1, 2]
    assert c["away_timeouts"].tolist() == [7, 7, 7, 4, 4, 2, 2, 2, 2]


def test_fouls_to_give_follow_nba_rules():
    rows = [foul(i, 1, "PT09M00.00S", "v") for i in range(1, 4)]  # 3 fouls: 1 to give
    rows += [foul(4, 1, "PT08M00.00S", "v", "Offensive")]  # offensive fouls don't count
    rows += [foul(5, 1, "PT07M00.00S", "v")]  # 4th: in the penalty
    rows += [play(6, 2, "PT03M00.00S", "", "period")]  # new quarter: 4 to give
    rows += [play(7, 2, "PT01M59.00S", "", "Rebound")]  # last 2 minutes: only 1 to give
    rows += [foul(8, 2, "PT01M30.00S", "v")]  # used it
    rows += [play(9, 5, "PT04M00.00S", "", "period")]  # overtime: 3 to give
    c = _counts(rows)
    assert c["away_fouls_to_give"].tolist() == [3, 2, 1, 1, 0, 4, 1, 0, 3]
    assert c["home_fouls_to_give"].tolist() == [4, 4, 4, 4, 4, 4, 1, 1, 3]
