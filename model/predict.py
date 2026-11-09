"""Load a trained model and score game states.

The API imports ``predict`` (one state) and ``predict_frame`` (many rows).
Nothing here imports torch: the MLP runs from exported numpy weights.

A *state* is a dict with the feature names from ``pipeline.features.FEATURES``.
``margin_x_time`` is filled in if it's missing, so callers can pass just::

    predict({"margin": 8, "seconds_left": 120, "is_ot": 0,
             "home_possession": 1, "strength_gap": 2.5})
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from model.mlp import forward_numpy
from pipeline import config
from pipeline.features import FEATURES

MODEL_NAMES = ("logreg", "xgboost", "mlp", "endgame")

# End-of-game model (docs/EXPERIMENTS.md, E4): XGBoost trained only on the last
# 3 minutes, blended into the best whole-game model as the clock runs down so
# the chart never jumps: none of it at 3:00 left, all of it from 2:00 on.
ENDGAME_START = 180.0
ENDGAME_FULL = 120.0
_SECONDS_LEFT = FEATURES.index("seconds_left")


def endgame_weight(seconds_left) -> np.ndarray:
    """How much the end-of-game model counts, 0 to 1, by seconds left."""
    t = np.asarray(seconds_left, dtype=np.float64)
    return np.clip((ENDGAME_START - t) / (ENDGAME_START - ENDGAME_FULL), 0.0, 1.0)

# XGBoost sees team strength rounded to whole points. strength_gap is the same
# for every play in a game and nearly unique to it, so at full precision the
# trees can single out individual training games and memorize how they ended
# (docs/EXPERIMENTS.md, E3).
XGB_STRENGTH_STEP = 1.0


def xgb_inputs(x: np.ndarray) -> np.ndarray:
    """Feature matrix as XGBoost sees it, in training and serving alike."""
    x = np.array(x, dtype=np.float32, copy=True)
    i = FEATURES.index("strength_gap")
    x[:, i] = np.round(x[:, i] / XGB_STRENGTH_STEP) * XGB_STRENGTH_STEP
    return x


class WinProbModel:
    def __init__(self, name: str, artifacts_dir: Path):
        self.name = name
        self.dir = Path(artifacts_dir)
        if name == "logreg":
            import joblib

            self._clf = joblib.load(self.dir / "logreg.joblib")
        elif name == "xgboost":
            import xgboost as xgb

            self._booster = xgb.Booster()
            self._booster.load_model(self.dir / "xgboost.json")
        elif name == "mlp":
            with np.load(self.dir / "mlp.npz") as f:
                self._params = {k: f[k] for k in f.files}
        elif name == "endgame":
            import xgboost as xgb

            self._late = xgb.Booster()
            self._late.load_model(self.dir / "endgame_xgb.json")
            # The whole-game model it hands over from, recorded at training time.
            self.base = self._late.attr("base") or "logreg"
            self._base = WinProbModel(self.base, self.dir)
        else:
            raise ValueError(f"unknown model {name!r}")
        # Optional isotonic calibration (model.train --calibrate): a monotone
        # lookup table from raw probability to calibrated probability.
        self._calibration = None
        cal = self.dir / f"{name}_calibration.npz"
        if cal.exists():
            with np.load(cal) as f:
                self._calibration = (f["x"], f["y"])

    def predict_array(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)
        if self.name == "logreg":
            p = self._clf.predict_proba(x)[:, 1]
        elif self.name == "xgboost":
            import xgboost as xgb

            p = self._booster.predict(xgb.DMatrix(xgb_inputs(x), feature_names=FEATURES))
        elif self.name == "endgame":
            p = self._base.predict_array(x)
            w = endgame_weight(x[:, _SECONDS_LEFT])
            late = w > 0
            if late.any():
                import xgboost as xgb

                q = self._late.predict(xgb.DMatrix(xgb_inputs(x[late]), feature_names=FEATURES))
                p = p.copy()
                p[late] = (1 - w[late]) * p[late] + w[late] * q
        else:
            p = forward_numpy(self._params, x)
        return np.clip(self.calibrate(p.astype(np.float64)), 1e-6, 1 - 1e-6)

    def calibrate(self, p: np.ndarray) -> np.ndarray:
        if self._calibration is None:
            return p
        xs, ys = self._calibration
        return np.interp(p, xs, ys)

    @property
    def calibrated(self) -> bool:
        return self._calibration is not None

    def predict_frame(self, df: pd.DataFrame) -> np.ndarray:
        return self.predict_array(df[FEATURES].to_numpy(dtype=np.float32))

    def predict(self, state: dict) -> float:
        return float(self.predict_array(np.array([state_vector(state)]))[0])


def state_vector(state: dict) -> list[float]:
    s = dict(state)
    if "margin_x_time" not in s:
        s["margin_x_time"] = s["margin"] / math.sqrt(s["seconds_left"] + 1.0)
    s.setdefault("is_ot", 0)
    s.setdefault("home_possession", 0.5)
    s.setdefault("strength_gap", 0.0)
    return [float(s[f]) for f in FEATURES]


def load_meta(artifacts_dir: Path | None = None) -> dict:
    path = Path(artifacts_dir or config.ARTIFACTS_DIR) / "meta.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=8)
def load_model(name: str | None = None, artifacts_dir: str | None = None) -> WinProbModel:
    """The named model, or the production model picked at training time."""
    adir = Path(artifacts_dir) if artifacts_dir else config.ARTIFACTS_DIR
    name = name or load_meta(adir)["production"]
    return WinProbModel(name, adir)


def predict(state: dict, model: str | None = None) -> float:
    """Home win probability for one game state."""
    return load_model(model).predict(state)


def predict_frame(df: pd.DataFrame, model: str | None = None) -> np.ndarray:
    return load_model(model).predict_frame(df)
