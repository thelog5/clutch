"""Acceptance: no game from the test season appears in training data.

The unit tests check the split logic on a small frame. The data tests run on
whatever ``features.parquet`` exists (real or, with CLUTCH_DATA_DIR, synthetic)
and on the trained model's recorded split, and skip when there's no data yet.
"""

import json

import pandas as pd
import pytest

from model.data import Split, assert_disjoint, split_by_season
from pipeline import config


def toy_features():
    rows = []
    for season in [*config.SEASONS, config.CURRENT_SEASON]:
        for g in range(3):
            for play in range(4):
                rows.append({"game_id": f"{season}-{g}", "season": season, "action_number": play})
    return pd.DataFrame(rows)


def test_split_is_by_season():
    s = split_by_season(toy_features())
    assert set(s.train["season"]) == set(config.TRAIN_SEASONS)
    assert set(s.val["season"]) == {config.VAL_SEASON}
    assert set(s.test["season"]) == {config.TEST_SEASON}


def test_current_season_is_never_trained_on():
    s = split_by_season(toy_features())
    for part in (s.train, s.val, s.test):
        assert config.CURRENT_SEASON not in set(part["season"])


def test_test_games_not_in_train():
    s = split_by_season(toy_features())
    assert not set(s.test["game_id"]) & set(s.train["game_id"])


def test_overlap_is_caught():
    f = toy_features()
    train = f[f["season"].isin(config.TRAIN_SEASONS)]
    test = f[f["season"] == config.TEST_SEASON]
    leaked = pd.concat([train, test.head(4)])  # one test game sneaks into train
    with pytest.raises(AssertionError):
        assert_disjoint(Split(train=leaked, val=f.iloc[:0], test=test))


def test_overlapping_seasons_rejected():
    with pytest.raises(ValueError):
        split_by_season(toy_features(), train_seasons=["2021-22", "2025-26"])


@pytest.fixture(scope="module")
def real_split():
    if not config.FEATURES_PATH.exists():
        pytest.skip(f"no features at {config.FEATURES_PATH}; run `make features`")
    cols = ["game_id", "season"]
    return split_by_season(pd.read_parquet(config.FEATURES_PATH, columns=cols))


def test_data_no_test_season_game_in_train(real_split):
    train_games = set(real_split.train["game_id"])
    test_games = set(real_split.test["game_id"])
    assert test_games, "test season has no games"
    assert not train_games & test_games
    assert config.TEST_SEASON not in set(real_split.train["season"])


def test_trained_model_split_excludes_test_season():
    meta_path = config.ARTIFACTS_DIR / "meta.json"
    if not meta_path.exists():
        pytest.skip("no trained model yet; run `make train`")
    meta = json.loads(meta_path.read_text())
    assert config.TEST_SEASON not in meta["split"]["train"]["seasons"]
    assert config.TEST_SEASON not in meta["split"]["val"]["seasons"]
    assert meta["split"]["test"]["seasons"] == [config.TEST_SEASON]


def test_readme_results_block_replaced(tmp_path):
    from model.evaluate import README_END, README_START, update_readme

    readme = tmp_path / "README.md"
    readme.write_text(f"# X\n\n## Results\n\n{README_START}\nPending\n{README_END}\n\n## Next\n")
    assert update_readme("| a | b |\n\\1 literal backref text", readme)
    text = readme.read_text()
    assert "Pending" not in text and "\\1 literal backref text" in text
    assert text.count("## Results") == 1 and text.endswith("## Next\n")
    readme.write_text("# no markers\n")
    assert not update_readme("x", readme)
