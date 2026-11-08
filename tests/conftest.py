"""Shared fixture: a tiny self-contained dataset + model + API bundle.

Simulates a handful of games with ``pipeline.synthetic``, builds features,
fits a logistic regression on them, and writes the API bundle to a temp dir.
Tests never depend on ``data/`` existing.
"""

import json
import random

import joblib
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.actions import from_v3
from pipeline.features import FEATURES, build_features
from pipeline.synthetic import V3_COLUMNS, GameSim
from pipeline.teams import BY_ABBR

MATCHUPS = [("TOR", "BOS"), ("LAL", "GSW"), ("TOR", "NYK"), ("MIA", "TOR"), ("DEN", "PHX"), ("BOS", "MIA")]


@pytest.fixture(scope="session")
def bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("bundle")
    rng = random.Random(3)
    plays, games = [], []
    for n, (h, a) in enumerate(MATCHUPS):
        gid = f"T{n:04d}"
        season = "2025-26" if n < 4 else "2026-27"
        home, away = BY_ABBR[h], BY_ABBR[a]
        sim = GameSim(rng, gid, home, away, 3.0, -1.0)
        raw = pd.DataFrame(sim.play(), columns=V3_COLUMNS)
        plays.append(from_v3(raw, home_team_id=home["id"]))
        games.append(
            {
                "game_id": gid,
                "season": season,
                "season_type": "Regular Season",
                "game_date": f"2026-0{n + 1}-15" if season == "2025-26" else f"2026-11-0{n}",
                "home_team_id": home["id"],
                "home_abbr": h,
                "home_name": f"{home['city']} {home['name']}",
                "away_team_id": away["id"],
                "away_abbr": a,
                "away_name": f"{away['city']} {away['name']}",
                "home_pts": sim.score["h"],
                "away_pts": sim.score["v"],
                "home_win": int(sim.score["h"] > sim.score["v"]),
            }
        )
    games = pd.DataFrame(games)
    feats = build_features(pd.concat(plays, ignore_index=True), {g: 2.0 for g in games["game_id"]})
    feats = feats.join(games.set_index("game_id")[["season", "home_win"]], on="game_id")

    artifacts = root / "artifacts"
    artifacts.mkdir()
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))
    clf.fit(feats[FEATURES].to_numpy("float32"), feats["home_win"])
    joblib.dump(clf, artifacts / "logreg.joblib")
    (artifacts / "meta.json").write_text(json.dumps({"production": "logreg", "models": ["logreg"]}))

    from api.precompute import write_bundle
    from model.predict import WinProbModel

    api_dir = root / "api"
    write_bundle(feats, games, WinProbModel("logreg", artifacts), api_dir, synthetic=True)
    return {"root": root, "api_dir": api_dir, "artifacts": artifacts, "games": games, "features": feats}


@pytest.fixture
def api_settings(bundle, monkeypatch):
    from api import settings

    d = bundle["api_dir"]
    monkeypatch.setattr(settings, "API_DATA_DIR", d)
    monkeypatch.setattr(settings, "SERIES_PATH", d / "series.parquet")
    monkeypatch.setattr(settings, "GAMES_PATH", d / "games.parquet")
    monkeypatch.setattr(settings, "STRENGTH_PATH", d / "team_strength.json")
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", bundle["artifacts"])
    monkeypatch.setattr(settings, "REPORTS_DIR", bundle["root"] / "reports")  # none: card has no test results
    monkeypatch.setattr(settings, "LIVE_SOURCE", "off")
    return settings


@pytest.fixture
def client(api_settings):
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c
