"""E5: how long should the end-game window be? Validation season only.

Run from the repo root: PYTHONPATH=. .venv/bin/python docs/experiments/e5_endgame_window.py
"""

import numpy as np
import pandas as pd
import xgboost as xgb

from model.data import split_by_season, xy
from model.predict import load_model, xgb_inputs
from model.train import ENDGAME_PARAMS, train_xgboost
from pipeline import config
from pipeline.features import FEATURES

f = pd.read_parquet(config.FEATURES_PATH)
sp = split_by_season(f)
tr, va = sp.train, sp.val
p_base = load_model("logreg").predict_frame(va)
y = va.home_win.to_numpy()
t = va.seconds_left.to_numpy()
reg = (va.is_ot == 0).to_numpy()
m = np.abs(va.margin.to_numpy())
segs = {
    "all": np.ones(len(va), bool),
    "6-3 min": reg & (t > 180) & (t <= 360),
    "last 3": reg & (t <= 180),
    "last 30 s": reg & (t > 0) & (t <= 30),
    "close 30 s": reg & (t > 0) & (t <= 30) & (m <= 3),
}
print(f"{'window (start -> full)':24}" + "".join(f"{k:>12}" for k in segs))


def show(label, p):
    print(f"{label:24}" + "".join(f"{((p[v] - y[v]) ** 2).mean():12.5f}" for v in segs.values()))


show("baseline only", p_base)
for start, full in [(180, 120), (300, 240), (360, 240), (480, 360), (720, 600)]:
    late, late_val = tr[tr.seconds_left <= start], va[va.seconds_left <= start]
    (x, yy), (xv, yv) = xy(late), xy(late_val)
    b = train_xgboost(x, yy, xv, yv, **ENDGAME_PARAMS)
    w = np.clip((start - t) / (start - full), 0, 1)
    idx = w > 0
    p = p_base.copy()
    p[idx] = (1 - w[idx]) * p_base[idx] + w[idx] * b.predict(
        xgb.DMatrix(xgb_inputs(va[FEATURES].to_numpy(float)[idx]), feature_names=FEATURES)
    )
    show(f"{start // 60}:{start % 60:02d} -> {full // 60}:{full % 60:02d} ({b.num_boosted_rounds()})", p)
