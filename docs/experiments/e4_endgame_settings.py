"""E4: pick the end-of-game model settings on the validation season.

Run from the repo root: PYTHONPATH=. .venv/bin/python docs/experiments/e4_endgame_settings.py
Trains an XGBoost model on the last 3 minutes only and blends it into the
baseline from 3:00 (0%) to 2:00 (100%). Results are in docs/EXPERIMENTS.md, E4.
"""

import json

import numpy as np
import pandas as pd
import xgboost as xgb

from model.data import split_by_season
from model.predict import load_model, xgb_inputs
from pipeline import config
from pipeline.features import FEATURES

f = pd.read_parquet(config.FEATURES_PATH)
sp = split_by_season(f)
tr, va = sp.train, sp.val
base = load_model("logreg")
p_base = base.predict_frame(va)
y = va.home_win.to_numpy()
t = va.seconds_left.to_numpy()
reg = (va.is_ot == 0).to_numpy()
m = va.margin.to_numpy()
segs = {
    "all": np.ones(len(va), bool),
    "last2": reg & (t <= 120),
    "last30": reg & (t > 0) & (t <= 30),
    "close30": reg & (t > 0) & (t <= 30) & (np.abs(m) <= 3),
}
probes = [dict(margin=-2, seconds_left=10, home_possession=1), dict(margin=0, seconds_left=5, home_possession=1)]


def extra(df):  # E1's possession x time, 0 at 0:00
    t = df["seconds_left"].to_numpy(float)
    return np.where(t > 0, (2 * df["home_possession"].to_numpy(float) - 1) / np.sqrt(t + 1), 0.0)


def matrix(df, with_pxt):
    x = xgb_inputs(df[FEATURES].to_numpy(float))
    return np.column_stack([x, extra(df)]) if with_pxt else x


def weight(t, start=180, full=120):
    return np.clip((start - t) / (start - full), 0, 1)


def report(label, p, extra_txt=""):
    sc = {k: ((p[v] - y[v]) ** 2).mean() for k, v in segs.items()}
    print(f"{label:44} {sc['all']:.5f} {sc['last2']:.5f} {sc['last30']:.5f} {sc['close30']:.5f} {extra_txt}")


print(f"{'validation Brier':44} {'all':>7} {'last2':>7} {'last30':>7} {'close30':>7}")
report("baseline (logreg)", p_base)

WINDOW = 180
trl, val_late = tr[tr.seconds_left <= WINDOW], va[va.seconds_left <= WINDOW]
print(f"late rows: train {len(trl):,} ({trl.game_id.nunique():,} games), val {len(val_late):,}")
for with_pxt in (False, True):
    names = FEATURES + (["possession_x_time"] if with_pxt else [])
    groups = [
        ["margin", "seconds_left", "is_ot", "home_possession", "margin_x_time"]
        + (["possession_x_time"] if with_pxt else []),
        ["strength_gap", "seconds_left", "is_ot"],
    ]
    mono = {"margin": 1, "home_possession": 1, "strength_gap": 1, "margin_x_time": 1, "possession_x_time": 1}
    dtr = xgb.DMatrix(matrix(trl, with_pxt), label=trl.home_win, feature_names=names)
    dvl = xgb.DMatrix(matrix(val_late, with_pxt), label=val_late.home_win, feature_names=names)
    dva = xgb.DMatrix(matrix(va, with_pxt), feature_names=names)
    for depth, mcw in [(4, 50), (6, 50), (6, 200), (6, 1000)]:
        params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "tree_method": "hist",
            "max_depth": depth,
            "eta": 0.05,
            "subsample": 0.8,
            "min_child_weight": mcw,
            "seed": 0,
            "monotone_constraints": "(" + ",".join(str(mono.get(n, 0)) for n in names) + ")",
            "interaction_constraints": json.dumps([[names.index(c) for c in g] for g in groups]),
        }
        b = xgb.train(params, dtr, 3000, evals=[(dvl, "val")], early_stopping_rounds=50, verbose_eval=False)
        b = b[: b.best_iteration + 1]
        w = weight(t)
        p = p_base.copy()
        idx = w > 0
        p[idx] = (1 - w[idx]) * p_base[idx] + w[idx] * b.predict(
            xgb.DMatrix(matrix(va[idx], with_pxt), feature_names=names)
        )
        pr = []
        for s in probes:
            row = pd.DataFrame([{**{"is_ot": 0, "strength_gap": 0.0}, **s}])
            row["margin_x_time"] = row.margin / np.sqrt(row.seconds_left + 1)
            pr.append(f"{b.predict(xgb.DMatrix(matrix(row, with_pxt), feature_names=names))[0]:.0%}")
        report(
            f"blend: xgb depth {depth} leaf {mcw}{' +pxt' if with_pxt else ''} ({b.num_boosted_rounds()} trees)",
            p,
            f"| down2 10s ball {pr[0]} (real 18%), tied 5s ball {pr[1]} (real 67%)",
        )
