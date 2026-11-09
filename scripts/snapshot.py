"""Save the evidence for one model version in docs/evidence/runs/<run>/.

    .venv/bin/python -m scripts.snapshot R3-fouls --label "Timeouts and fouls (E6)"
    .venv/bin/python -m scripts.snapshot R0-original --artifacts /tmp/r0 --commit 93f8cd9 --label "..."

Numbers first, so every chart can be redrawn later (docs/evidence/compare.py):

  setup.json       how it was trained: seasons, games, plays, inputs, models, settings, commit, file hashes
  metrics.csv      Brier and log loss with play and game counts, per model x season x game situation
  calibration.csv  test-season calibration bins per model
  situations.csv   fixed what-if situations: each model's answer next to real games
  cases.csv        the frozen real game moments (docs/evidence/cases.csv), scored by each model
  reality.csv      model vs real games for every score x time x possession cell (the explorer's error map)
  calibration.png  calibration chart
  explorer.html    the model explorer for this version
  explorer.png     a screenshot of the explorer (--screenshot; needs Google Chrome)

One-time setup (already done; rerun only if the data changes):
  --pick-cases     choose the real game moments every version is scored on
  --write-split    write the game IDs in the training, validation and test seasons
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from model.data import load_features, split_by_season
from model.evaluate import evaluate_model, plot_calibration
from model.predict import WinProbModel, load_meta
from pipeline import config
from pipeline.actions import format_clock
from scripts import model_explorer

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
CASES = EVIDENCE / "cases.csv"
OUT_OF_SAMPLE = [config.VAL_SEASON, config.TEST_SEASON]

# Game situations every version is scored on: "metrics.csv" rows.
SEGMENTS = {
    "whole game": lambda d: np.ones(len(d), bool),
    "first half": lambda d: d["period"] <= 2,
    "fourth quarter": lambda d: (d["period"] == 4) & (d["is_ot"] == 0),
    "last 2 minutes": lambda d: (d["is_ot"] == 0) & (d["seconds_left"] <= 120),
    "last 30 seconds": lambda d: (d["is_ot"] == 0) & (d["seconds_left"] > 0) & (d["seconds_left"] <= 30),
    "close, last 2 minutes": lambda d: (d["is_ot"] == 0) & (d["seconds_left"] <= 120) & (d["margin"].abs() <= 3),
    "close, last 30 seconds": lambda d: (d["is_ot"] == 0) & (d["seconds_left"] > 0) & (d["seconds_left"] <= 30)
    & (d["margin"].abs() <= 3),
    "overtime": lambda d: d["is_ot"] == 1,
}

# What-if situations: (name, state, real-game match: seconds-left window and possession, None = any).
SITUATIONS = [
    ("Tipoff, evenly matched", {"margin": 0, "seconds_left": 2880, "home_possession": 0.5}, (2820, 2880), None),
    ("Up 8 at halftime", {"margin": 8, "seconds_left": 1440, "home_possession": 0.5}, (1400, 1480), None),
    ("Up 8, 2 min left, home ball", {"margin": 8, "seconds_left": 120, "home_possession": 1}, (105, 135), 1),
    ("Up 3, 30 s left, away ball", {"margin": 3, "seconds_left": 30, "home_possession": 0}, (20, 40), 0),
    ("Down 1, 20 s left, home ball", {"margin": -1, "seconds_left": 20, "home_possession": 1}, (15, 25), 1),
    ("Down 2, 10 s left, home ball", {"margin": -2, "seconds_left": 10, "home_possession": 1}, (5, 15), 1),
    ("Down 2, 10 s left, away ball", {"margin": -2, "seconds_left": 10, "home_possession": 0}, (5, 15), 0),
    ("Down 3, 15 s left, home ball", {"margin": -3, "seconds_left": 15, "home_possession": 1}, (10, 20), 1),
    ("Tied, 5 s left, home ball", {"margin": 0, "seconds_left": 5, "home_possession": 1}, (3, 8), 1),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def game_weighted(rows: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Each game counts once: average its plays first, then average the games."""
    return rows.groupby("game_id")[cols].mean().mean()


# ---------- one-time setup ----------


def write_split(features: pd.DataFrame) -> None:
    games = pd.read_parquet(config.GAMES_PATH).set_index("game_id")
    split = split_by_season(features)
    out = EVIDENCE / "split"
    out.mkdir(parents=True, exist_ok=True)
    for part, df in (("train", split.train), ("validation", split.val), ("test", split.test)):
        ids = sorted(df["game_id"].unique())
        g = games.loc[ids, ["season", "game_date", "away_abbr", "home_abbr", "away_pts", "home_pts"]]
        g.reset_index().to_csv(out / f"{part}.csv", index=False)
        print(f"{part}: {len(ids)} games -> {out / f'{part}.csv'}")


def pick_cases(features: pd.DataFrame, artifacts: Path, n: int = 12) -> None:
    """The original model's worst calls in close finishes of the test season, frozen for every later version.

    Rule: test season, regulation, 0:30 to 0:01 left, within 3 points, possession known. For each game take
    the play where the original production model was furthest from the result; keep the n furthest games.
    """
    meta = load_meta(artifacts)
    model = WinProbModel(meta["production"], artifacts)
    test = features[features["season"] == config.TEST_SEASON]
    late = test[(test["is_ot"] == 0) & (test["seconds_left"] > 0) & (test["seconds_left"] <= 30)
                & (test["margin"].abs() <= 3) & test["home_possession"].isin([0.0, 1.0])].copy()  # fmt: skip
    late["p"] = model.predict_frame(late)
    late["miss"] = (late["home_win"] - late["p"]).abs()
    worst = late.loc[late.groupby("game_id")["miss"].idxmax()].nlargest(n, "miss")

    games = pd.read_parquet(config.GAMES_PATH).set_index("game_id")
    rows = []
    for _, r in worst.iterrows():
        g = games.loc[r["game_id"]]
        after = test[(test["game_id"] == r["game_id"]) & (test.index > r.name)]
        scoring = after[after["action_type"].isin(["Made Shot", "Free Throw"])
                        & ~after["description"].str.upper().str.startswith("MISS")].head(4)  # fmt: skip
        went_ot = bool((test.loc[test["game_id"] == r["game_id"], "is_ot"] == 1).any())
        lead = int(r["margin"])
        rows.append(
            {
                "case": f"C{len(rows) + 1:02d}",
                "game_id": r["game_id"],
                "action_number": int(r["action_number"]),
                "date": g["game_date"],
                "matchup": f"{g['away_abbr']} at {g['home_abbr']}",
                "clock": f"Q4 {format_clock(r['clock_secs'])}",
                "score_away_home": f"{int(r['away_score'])}-{int(r['home_score'])}",
                "situation": ("Tied" if lead == 0 else f"Home {'up' if lead > 0 else 'down'} {abs(lead)}")
                + (", home ball" if r["home_possession"] == 1 else ", away ball"),
                "original_model": meta["production"],
                "original_home_win_prob": round(float(r["p"]), 4),
                "result": f"Home {'won' if r['home_win'] else 'lost'} {int(g['home_pts'])}-{int(g['away_pts'])}"
                + (" in overtime" if went_ot else ""),
                "what_happened_next": " | ".join(
                    f"{format_clock(s['clock_secs'])} {s['description']}" for _, s in scoring.iterrows()
                ),
            }
        )
    pd.DataFrame(rows).to_csv(CASES, index=False)
    print(f"{len(rows)} cases -> {CASES}")


# ---------- one version ----------


def snapshot(run: str, label: str, artifacts: Path, commit: str, features: pd.DataFrame,
             settings: dict, screenshot: bool) -> Path:  # fmt: skip
    out = EVIDENCE / "runs" / run
    out.mkdir(parents=True, exist_ok=True)
    meta = load_meta(artifacts)
    models = {n: WinProbModel(n, artifacts) for n in meta["models"]}
    split = split_by_season(features)

    setup = {
        "run": run,
        "label": label,
        "snapshot_taken": dt.datetime.now().isoformat(timespec="seconds"),
        "commit": commit,
        "artifact_sha256": {p.name: sha256(p) for p in sorted(artifacts.iterdir()) if p.is_file()},
        "trained_at": meta.get("trained_at"),
        "data_source": meta.get("data_source"),
        "inputs": meta.get("features"),
        "models": meta["models"],
        "production": meta["production"],
        "split": meta.get("split"),
        "validation_scores": meta.get("val"),
        "settings": {k: meta[k] for k in ("xgboost_trees", "xgboost_strength_step", "endgame", "settings")
                     if k in meta} | settings,  # fmt: skip
    }
    (out / "setup.json").write_text(json.dumps(setup, indent=2) + "\n")

    # metrics.csv
    rows = []
    for role, part in (("validation", split.val), ("test", split.test)):
        preds = {n: m.predict_frame(part) for n, m in models.items()}
        y = part["home_win"].to_numpy()
        for seg, f in SEGMENTS.items():
            mask = np.asarray(f(part))
            if not mask.any():
                continue
            for n, p in preds.items():
                pm, ym = p[mask], y[mask]
                rows.append({
                    "run": run, "model": n, "on_site": n == meta["production"], "season_role": role,
                    "season": part["season"].iloc[0], "segment": seg, "plays": int(mask.sum()),
                    "games": int(part.loc[mask, "game_id"].nunique()),
                    "brier": round(float(np.mean((pm - ym) ** 2)), 6),
                    "log_loss": round(float(-np.mean(ym * np.log(pm) + (1 - ym) * np.log(1 - pm))), 6),
                    "mean_pred": round(float(pm.mean()), 4), "home_win_rate": round(float(ym.mean()), 4),
                })  # fmt: skip
    pd.DataFrame(rows).to_csv(out / "metrics.csv", index=False)

    # calibration.csv + calibration.png (test season)
    results, cal = {}, []
    for n in models:
        results[n], bins = evaluate_model(n, split.test, artifacts)
        cal.append(bins.assign(model=n))
    pd.concat(cal).round(6).to_csv(out / "calibration.csv", index=False)
    plot_calibration(results, out / "calibration.png")

    # situations.csv
    oos = features[features["season"].isin(OUT_OF_SAMPLE) & (features["is_ot"] == 0)]
    srows = []
    for name, state, (lo, hi), poss in SITUATIONS:
        match = oos[(oos["margin"] == state["margin"]) & oos["seconds_left"].between(lo, hi)]
        if poss is not None:
            match = match[match["home_possession"] == poss]
        row = {"situation": name, **{f"state_{k}": v for k, v in state.items()},
               "real_games": int(match["game_id"].nunique())}  # fmt: skip
        if len(match):
            avg = game_weighted(match.assign(**{f"avg_{n}": m.predict_frame(match) for n, m in models.items()}),
                                ["home_win", *[f"avg_{n}" for n in models]])  # fmt: skip
            row["real_home_win_rate"] = round(float(avg["home_win"]), 4)
        for n, m in models.items():
            row[f"pred_{n}"] = round(m.predict(state), 4)
            if len(match):
                row[f"avg_pred_on_real_{n}"] = round(float(avg[f"avg_{n}"]), 4)
        srows.append(row)
    pd.DataFrame(srows).to_csv(out / "situations.csv", index=False)

    # cases.csv
    if CASES.exists():
        cases = pd.read_csv(CASES, dtype={"game_id": str})
        keyed = features.set_index(["game_id", "action_number"])
        at = keyed.loc[list(zip(cases["game_id"], cases["action_number"], strict=True))].reset_index()
        scored = cases[["case", "game_id", "action_number", "situation", "result"]].copy()
        for n, m in models.items():
            scored[f"pred_{n}"] = np.round(m.predict_frame(at), 4)
        scored.to_csv(out / "cases.csv", index=False)

    # reality.csv + explorer
    with tempfile.TemporaryDirectory() as tmp:
        adir = Path(tmp)
        for p in artifacts.iterdir():
            if p.is_file():
                shutil.copy(p, adir / p.name)
        (adir / "metrics.json").write_text(json.dumps({"models": results}))  # the explorer's score table
        model_explorer.write(adir, out / "explorer.html")
        real = model_explorer.reality({n: WinProbModel(n, adir) for n in models}, OUT_OF_SAMPLE)
    long = []
    for pi, poss in enumerate(model_explorer.POSSESSION):
        for mi, margin in enumerate(model_explorer.MARGINS):
            for ti, secs in enumerate(model_explorer.TIMES):
                g = real["games"][pi][mi][ti]
                if not g:
                    continue
                long.append({"home_possession": poss, "margin": margin, "seconds_left": secs, "games": g,
                             "real_home_win_rate": real["actual"][pi][mi][ti] / 1000,
                             **{f"avg_pred_{n}": real["pred"][n][pi][mi][ti] / 1000 for n in models}})  # fmt: skip
    pd.DataFrame(long).to_csv(out / "reality.csv", index=False)

    if screenshot:
        from scripts.screenshot import shoot

        shoot(f"file://{out / 'explorer.html'}", out / "explorer.png", wait=4, width=1280, height=4300)
    print(f"{run}: evidence -> {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("run", nargs="?", help="run id, e.g. R3-fouls")
    parser.add_argument("--label", default="")
    parser.add_argument("--artifacts", type=Path, default=config.ARTIFACTS_DIR)
    parser.add_argument("--commit", help="commit the artifacts came from (default: HEAD)")
    parser.add_argument("--settings", default="{}", help="extra training settings to record, as JSON")
    parser.add_argument("--screenshot", action="store_true")
    parser.add_argument("--pick-cases", action="store_true")
    parser.add_argument("--write-split", action="store_true")
    args = parser.parse_args()

    features = load_features()
    if args.write_split:
        write_split(features)
    if args.pick_cases:
        pick_cases(features, args.artifacts)
    if args.run:
        snapshot(args.run, args.label, args.artifacts, args.commit or git("rev-parse", "--short", "HEAD"),
                 features, json.loads(args.settings), args.screenshot)  # fmt: skip


if __name__ == "__main__":
    main()
