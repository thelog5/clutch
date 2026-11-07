"""Train all three models: ``python -m model.train``.

* logistic regression (baseline): standardized features, L2
* XGBoost: hist trees, early stopping on the validation season, monotone in
  margin / possession / strength_gap / margin_x_time
* PyTorch MLP: 2 hidden layers of 32 (``model/mlp.py``)

Train on 2021-22 to 2023-24, early-stop and pick the production model on
2024-25. The test season (2025-26) is never touched here; ``model.evaluate``
is the only thing that scores it.

Writes ``logreg.joblib``, ``xgboost.json``, ``mlp.npz`` and ``meta.json`` to
``config.ARTIFACTS_DIR``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import time

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from model import mlp
from model.data import load_features, split_by_season, xy
from model.predict import WinProbModel
from pipeline import config
from pipeline.features import FEATURES

log = logging.getLogger("model.train")

# +1: probability can only go up as the feature goes up; 0: unconstrained.
MONOTONE = {
    "margin": 1,
    "seconds_left": 0,
    "is_ot": 0,
    "home_possession": 1,
    "strength_gap": 1,
    "margin_x_time": 1,
}


def train_logreg(x, y):
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    clf.fit(x, y)
    return clf


def train_xgboost(x, y, xv, yv):
    import xgboost as xgb

    dtrain = xgb.DMatrix(x, label=y, feature_names=FEATURES)
    dval = xgb.DMatrix(xv, label=yv, feature_names=FEATURES)
    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "tree_method": "hist",
        "max_depth": 6,
        "eta": 0.05,
        "subsample": 0.8,
        "min_child_weight": 100,
        "lambda": 1.0,
        "monotone_constraints": "(" + ",".join(str(MONOTONE[f]) for f in FEATURES) + ")",
        "seed": 0,
    }
    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=3000,
        evals=[(dval, "val")],
        early_stopping_rounds=50,
        verbose_eval=100,
    )
    # Keep only the trees up to the best iteration.
    return booster[: booster.best_iteration + 1]


def fit_isotonic(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Isotonic map raw -> calibrated probability, as knots for np.interp."""
    from sklearn.isotonic import IsotonicRegression

    iso = IsotonicRegression(y_min=1e-4, y_max=1 - 1e-4, out_of_bounds="clip").fit(p, y)
    return iso.X_thresholds_.astype(np.float64), iso.y_thresholds_.astype(np.float64)


def _train_mlp_child(epochs: int, out_path: str) -> None:
    """Runs in a fresh process: see ``train_mlp_isolated``."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    split = split_by_season(load_features())
    x, y = xy(split.train)
    xv, yv = xy(split.val)
    params = mlp.train(x, y, xv, yv, epochs=epochs)
    params.pop("best_val_logloss")
    np.savez(out_path, **params)


def train_mlp_isolated(epochs: int, out_path) -> None:
    """Train the MLP in a spawned process.

    On macOS, XGBoost (Homebrew libomp) and PyTorch (its own bundled OpenMP)
    deadlock when both run OpenMP work in one process: torch hangs at 0% CPU
    after an XGBoost fit. A spawned child starts clean, with only torch loaded.
    """
    import multiprocessing as mp

    proc = mp.get_context("spawn").Process(target=_train_mlp_child, args=(epochs, str(out_path)))
    proc.start()
    proc.join()
    if proc.exitcode != 0:
        raise RuntimeError(f"MLP training process exited with {proc.exitcode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-mlp", action="store_true", help="R9 fallback: baseline + XGBoost only")
    parser.add_argument("--mlp-epochs", type=int, default=30)
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="fit isotonic calibration on the validation season and apply it at predict time",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    split = split_by_season(load_features())
    summary = split.summary()
    log.info("split: %s", json.dumps(summary))
    x, y = xy(split.train)
    xv, yv = xy(split.val)

    out = config.ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    timings = {}

    t = time.time()
    joblib.dump(train_logreg(x, y), out / "logreg.joblib")
    timings["logreg"] = time.time() - t
    log.info("logreg trained in %.1fs", timings["logreg"])

    t = time.time()
    booster = train_xgboost(x, y, xv, yv)
    booster.save_model(out / "xgboost.json")
    timings["xgboost"] = time.time() - t
    log.info("xgboost trained in %.1fs (%d trees)", timings["xgboost"], booster.num_boosted_rounds())

    names = ["logreg", "xgboost"]
    if not args.skip_mlp:
        t = time.time()
        train_mlp_isolated(args.mlp_epochs, out / "mlp.npz")
        timings["mlp"] = time.time() - t
        names.append("mlp")
        log.info("mlp trained in %.1fs", timings["mlp"])

    val_scores = {}
    for name in names:
        p = WinProbModel(name, out).predict_array(xv)
        val_scores[name] = {"brier": float(brier_score_loss(yv, p)), "log_loss": float(log_loss(yv, p))}
        log.info("val %-8s brier %.5f  logloss %.5f", name, *val_scores[name].values())

    # Chosen on raw validation scores; calibration below is fit on the same season.
    production = min(val_scores, key=lambda n: val_scores[n]["brier"])

    for name in names:
        cal_path = out / f"{name}_calibration.npz"
        if cal_path.exists():
            cal_path.unlink()
        if args.calibrate:
            xs, ys = fit_isotonic(WinProbModel(name, out).predict_array(xv), yv)
            np.savez(cal_path, x=xs, y=ys)
            log.info("%s: isotonic calibration with %d knots", name, len(xs))
    meta = {
        "trained_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": config.data_source(),
        "features": FEATURES,
        "models": names,
        "production": production,
        "split": summary,
        "val": val_scores,
        "calibrated": bool(args.calibrate),
        "train_seconds": timings,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    log.info("production model (best val Brier): %s -> %s", production, out)


if __name__ == "__main__":
    main()
