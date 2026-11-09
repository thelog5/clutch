"""Write reports/explorer.html, a page for looking inside the trained models.

    .venv/bin/python -m scripts.model_explorer        (or: make explore)

Scores every model on a grid of game states (score margin x time left x who
has the ball x team strength), lines that up with what really happened in the
validation and test seasons (games the models never trained on), and fills
the numbers into scripts/explorer_template.html. Rerun after every
`make train` to see what changed. Needs data/features.parquet and the trained
models in model/artifacts/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from model.predict import load_meta, load_model
from pipeline import config
from pipeline.features import FEATURES

TEMPLATE = Path(__file__).with_name("explorer_template.html")
OUT = config.REPORTS_DIR / "explorer.html"

MARGINS = list(range(-15, 16))
# Seconds left in regulation. Evenly spaced on the page, so the final minutes
# get as much room as the first half.
TIMES = [2880, 2160, 1440, 1080, 720, 600, 480, 360, 300, 240, 180, 120, 90, 60, 45, 30, 20, 15, 10, 5, 2]
POSSESSION = [0.0, 0.5, 1.0]  # away ball, unknown, home ball
STRENGTH = [-6.0, -3.0, 0.0, 3.0, 6.0]  # home minus away point differential per game
MIN_GAMES = 20  # reality cells with fewer games are shown as "not enough games"


def state_frame(margin, seconds_left, possession, strength) -> pd.DataFrame:
    df = pd.DataFrame(
        {"margin": margin, "seconds_left": seconds_left, "home_possession": possession, "strength_gap": strength}
    ).astype(float)
    df["is_ot"] = 0.0
    df["margin_x_time"] = df["margin"] / np.sqrt(df["seconds_left"] + 1.0)
    return df


def model_grid(models: dict) -> dict:
    """pred[model][strength][possession][margin][time], in tenths of a percent."""
    s, p, m, t = np.meshgrid(STRENGTH, POSSESSION, MARGINS, TIMES, indexing="ij")
    frame = state_frame(m.ravel(), t.ravel(), p.ravel(), s.ravel())
    return {
        name: np.rint(model.predict_frame(frame) * 1000).astype(int).reshape(s.shape).tolist()
        for name, model in models.items()
    }


def time_bins() -> np.ndarray:
    """Edges halfway between neighbouring grid times; bin j covers TIMES[j]."""
    t = np.array(TIMES, dtype=float)
    mids = (t[:-1] + t[1:]) / 2
    return np.concatenate([[np.inf], mids, [0.0]])


def reality(models: dict, seasons: list[str]) -> dict:
    """What happened in real games, per (possession, margin, time bin), game-weighted.

    Each game counts once per cell (its plays there are averaged first), so a
    game that sat at one score for a long stretch doesn't outvote the others.
    Strength isn't split out (too few games per cell); the models' numbers here
    are their average predictions on the same plays, so the comparison is fair.
    """
    cols = ["game_id", "season", "margin", "seconds_left", "is_ot", "home_possession", "home_win", *FEATURES]
    f = pd.read_parquet(config.FEATURES_PATH, columns=list(dict.fromkeys(cols)))
    f = f[f["season"].isin(seasons) & (f["is_ot"] == 0) & (f["seconds_left"] > 0) & (f["margin"].abs() <= 15)]
    edges = time_bins()
    f = f.assign(
        t_bin=np.searchsorted(-edges, -f["seconds_left"].to_numpy(), side="left") - 1,
        p_bin=f["home_possession"].map({0.0: 0, 0.5: 1, 1.0: 2}),
        m_bin=f["margin"].astype(int) + 15,
    )
    for name, model in models.items():
        f[name] = model.predict_frame(f)
    keys = ["p_bin", "m_bin", "t_bin"]
    per_game = f.groupby([*keys, "game_id"])[["home_win", *models]].mean()
    cells = per_game.groupby(keys).agg(games=("home_win", "size"), actual=("home_win", "mean"),
                                       **{n: (n, "mean") for n in models})  # fmt: skip

    shape = (len(POSSESSION), len(MARGINS), len(TIMES))
    games = np.zeros(shape, dtype=int)
    actual = np.full(shape, -1, dtype=int)
    preds = {n: np.full(shape, -1, dtype=int) for n in models}
    for (p, m, t), row in cells.iterrows():
        games[p, m, t] = row["games"]
        actual[p, m, t] = round(row["actual"] * 1000)
        for n in models:
            preds[n][p, m, t] = round(row[n] * 1000)
    return {
        "seasons": seasons,
        "games_total": int(f["game_id"].nunique()),
        "games": games.tolist(),
        "actual": actual.tolist(),
        "pred": {n: v.tolist() for n, v in preds.items()},
    }


def leans(models: dict) -> dict:
    """What each model leans on: baseline weights and each tree model's split gain."""
    out = {}
    if "logreg" in models:
        clf = models["logreg"]._clf
        coef = clf.named_steps["logisticregression"].coef_[0]
        out["logreg"] = {f: round(float(c), 3) for f, c in zip(FEATURES, coef, strict=True)}
    boosters = {"xgboost": lambda m: m._booster, "endgame": lambda m: m._late}
    for name, get in boosters.items():
        if name in models:
            gain = get(models[name]).get_score(importance_type="total_gain")
            total = sum(gain.values()) or 1.0
            out[name] = {f: round(gain.get(f, 0.0) / total, 4) for f in FEATURES}
    return out


def scores() -> dict:
    path = config.REPORTS_DIR / "metrics.json"
    if not path.exists():
        return {}
    m = json.loads(path.read_text())
    keep = ("brier", "log_loss", "ece", "max_bin_gap")
    return {n: {k: r[k] for k in keep} | {"last2": r["phases"].get("last_2_minutes", {}).get("brier")}
            for n, r in m["models"].items()}  # fmt: skip


def training_mix() -> dict:
    """How much of the training data looks like a close finish."""
    cols = ["game_id", "season", "margin", "seconds_left", "is_ot"]
    f = pd.read_parquet(config.FEATURES_PATH, columns=cols)
    f = f[f["season"].isin(config.TRAIN_SEASONS)]
    reg = f["is_ot"] == 0
    close = reg & (f["seconds_left"] > 0) & (f["seconds_left"] <= 30) & (f["margin"].abs() <= 3)
    first_half = reg & (f["seconds_left"] > 1440)
    return {
        "rows": int(len(f)),
        "games": int(f["game_id"].nunique()),
        "close_rows": int(close.sum()),
        "close_games": int(f.loc[close, "game_id"].nunique()),
        "first_half_rows": int(first_half.sum()),
    }


def build() -> dict:
    meta = load_meta()
    models = {n: load_model(n) for n in meta["models"]}
    return {
        "trained_at": meta["trained_at"],
        "data_source": meta.get("data_source", "nba"),
        "production": meta["production"],
        "split": meta["split"],
        "models": list(models),
        "features": FEATURES,
        "margins": MARGINS,
        "times": TIMES,
        "possession": POSSESSION,
        "strength": STRENGTH,
        "min_games": MIN_GAMES,
        "grid": model_grid(models),
        "reality": reality(models, [config.VAL_SEASON, config.TEST_SEASON]),
        "leans": leans(models),
        "scores": scores(),
        "mix": training_mix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--fragment", type=Path, help="also write the page without its document wrapper")
    args = parser.parse_args()

    data = json.dumps(build(), separators=(",", ":"))
    page = TEMPLATE.read_text().replace("/*__DATA__*/null", data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    head = (
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    )
    OUT.write_text(head + page)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")
    if args.fragment:
        args.fragment.write_text(page)


if __name__ == "__main__":
    main()
