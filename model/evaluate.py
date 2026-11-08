"""Evaluation report on the held-out test season: ``python -m model.evaluate``.

For every trained model:

* Brier score and log loss
* calibration over 10 equal-width bins, expected calibration error (ECE), and
  the worst bin's gap from the diagonal (acceptance: every bin within 5 points)
* scores by game phase: first half, third quarter, fourth quarter, last 2
  minutes (and overtime)
* sanity checks: the final play should be near 0 or 1, and at tipoff the
  probability should track strength_gap

Writes ``metrics.json``, ``eval.md`` and ``calibration.png`` (plus a dark
variant) to ``config.REPORTS_DIR``. On real data it also refreshes the results
block in the README.
"""

from __future__ import annotations

import json
import logging
import re

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from model.data import load_features, split_by_season
from model.predict import WinProbModel, load_meta
from pipeline import config

log = logging.getLogger("model.evaluate")

N_BINS = 10
MIN_BIN_ROWS = 200  # bins thinner than this are reported but don't fail acceptance
CALIBRATION_TOLERANCE = 0.05
LABELS = {"logreg": "Logistic regression", "xgboost": "XGBoost", "mlp": "MLP", "endgame": "End-game model"}

PHASES = {
    "first_half": lambda d: d["period"] <= 2,
    "third_quarter": lambda d: d["period"] == 3,
    "fourth_quarter": lambda d: d["period"] == 4,
    "last_2_minutes": lambda d: (d["period"] >= 4) & (d["seconds_left"] <= 120),
    "overtime": lambda d: d["is_ot"] == 1,
}


def calibration_bins(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS) -> pd.DataFrame:
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    df = pd.DataFrame({"bin": idx, "p": p, "y": y})
    g = df.groupby("bin").agg(n=("y", "size"), mean_pred=("p", "mean"), frac_pos=("y", "mean"))
    g = g.reindex(range(n_bins))
    g["lo"], g["hi"] = edges[:-1], edges[1:]
    g["gap"] = (g["frac_pos"] - g["mean_pred"]).abs()
    return g.reset_index()


def ece(bins: pd.DataFrame) -> float:
    b = bins.dropna(subset=["n"])
    return float((b["n"] / b["n"].sum() * b["gap"]).sum())


def score(y, p) -> dict:
    if len(y) == 0:
        return {"rows": 0}
    return {
        "rows": int(len(y)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
    }


def evaluate_model(name: str, test: pd.DataFrame, artifacts_dir=None) -> tuple[dict, pd.DataFrame]:
    y = test["home_win"].to_numpy()
    p = WinProbModel(name, artifacts_dir or config.ARTIFACTS_DIR).predict_frame(test)
    bins = calibration_bins(y, p)
    solid = bins[bins["n"] >= MIN_BIN_ROWS]
    out = score(y, p) | {
        "ece": ece(bins),
        "max_bin_gap": float(solid["gap"].max()),
        "calibrated_within_5pts": bool((solid["gap"] <= CALIBRATION_TOLERANCE).all()),
        "bins": bins.round(5).replace({np.nan: None}).to_dict(orient="records"),
        "phases": {ph: score(y[m], p[m]) for ph, f in PHASES.items() for m in [f(test).to_numpy()]},
    }

    # Sanity: last play of each game should be near 0 or 1.
    t = test.assign(p=p)
    last = t.groupby("game_id").tail(1)
    winner_prob = np.where(last["home_win"] == 1, last["p"], 1 - last["p"])
    out["final_play"] = {
        "mean_prob_on_winner": float(winner_prob.mean()),
        "share_above_0.95": float((winner_prob > 0.95).mean()),
    }
    # Sanity: at tipoff, probability should track strength_gap.
    first = t.groupby("game_id").head(1)
    out["tipoff"] = {
        "corr_with_strength_gap": float(np.corrcoef(first["p"], first["strength_gap"])[0, 1]),
        "mean_prob": float(first["p"].mean()),
        "home_win_rate": float(first["home_win"].mean()),
    }
    return out, bins


def plot_calibration(results: dict, path, dark: bool = False) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Reference palette slots 1-3 (validated all-pairs) + violet for the end-game
    # model, which only ever sits in its own panel, + chart chrome.
    if dark:
        surface, ink, ink2, muted, grid, axis = "#1a1a19", "#f0efec", "#c3c2b7", "#898781", "#2c2c2a", "#383835"
        series = {"logreg": "#3987e5", "xgboost": "#d95926", "mlp": "#199e70", "endgame": "#9085e9"}
    else:
        surface, ink, ink2, muted, grid, axis = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
        series = {"logreg": "#2a78d6", "xgboost": "#eb6834", "mlp": "#1baf7a", "endgame": "#6250d6"}

    names = list(results)
    fig, axes = plt.subplots(
        2, len(names), figsize=(4.2 * len(names), 5.6), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1]}, squeeze=False, facecolor=surface,
    )  # fmt: skip
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "sans-serif"]
    for col, name in enumerate(names):
        r = results[name]
        bins = pd.DataFrame(r["bins"]).dropna(subset=["n"])
        ax, hax = axes[0, col], axes[1, col]
        for a in (ax, hax):
            a.set_facecolor(surface)
            for side in ("top", "right"):
                a.spines[side].set_visible(False)
            for side in ("left", "bottom"):
                a.spines[side].set_color(axis)
            a.tick_params(colors=muted, labelsize=9, length=0)
            a.grid(color=grid, linewidth=0.8)
            a.set_axisbelow(True)

        diag = np.array([0, 1])
        ax.fill_between(diag, diag - CALIBRATION_TOLERANCE, diag + CALIBRATION_TOLERANCE,
                        color=muted, alpha=0.15, linewidth=0, label="±5 pts")  # fmt: skip
        ax.plot(diag, diag, color=muted, linewidth=1, linestyle=(0, (4, 3)))
        ax.plot(bins["mean_pred"], bins["frac_pos"], color=series.get(name, ink2), linewidth=2,
                marker="o", markersize=6, markeredgecolor=surface, markeredgewidth=1.5)  # fmt: skip
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(LABELS.get(name, name), color=ink, fontsize=12, loc="left", pad=22, fontweight="bold")
        stats = f"Brier {r['brier']:.4f} · ECE {r['ece'] * 100:.2f} pts · worst bin {r['max_bin_gap'] * 100:.1f} pts"
        ax.text(0, 1.04, stats,
                transform=ax.transAxes, color=ink2, fontsize=9)  # fmt: skip
        if col == 0:
            ax.set_ylabel("Share of plays the home team went on to win", color=ink2, fontsize=9)
            hax.set_ylabel("Plays", color=ink2, fontsize=9)

        width = 1 / N_BINS
        hax.bar(bins["lo"] + width / 2, bins["n"], width=width - 0.012, color=series.get(name, ink2), alpha=0.85)
        hax.set_xlabel("Predicted home win probability", color=ink2, fontsize=9)
        hax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v / 1e3:.0f}k" if v >= 1e3 else f"{v:.0f}"))  # fmt: skip

    fig.text(0.01, 0.985, "Calibration on the held-out test season", color=ink, fontsize=14,
             fontweight="bold", va="top")  # fmt: skip
    fig.text(0.01, 0.95, "Dashed line = perfect calibration; shaded band = within 5 points. 10 equal-width bins.",
             color=ink2, fontsize=9.5, va="top")  # fmt: skip
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=160, facecolor=surface)
    plt.close(fig)


def _sections(results: dict, meta: dict) -> dict:
    """Tables and checks shared by eval.md and the README results block."""
    names = list(results)
    head = "| Metric | " + " | ".join(LABELS.get(n, n) for n in names) + " |"
    sep = "| --- |" + " --- |" * len(names)

    def row(label, fn):
        return f"| {label} | " + " | ".join(fn(results[n]) for n in names) + " |"

    resume = [
        head,
        sep,
        row("Brier score", lambda r: f"{r['brier']:.4f}"),
        row("Log loss", lambda r: f"{r['log_loss']:.4f}"),
        row("Expected calibration error", lambda r: f"{r['ece']:.4f}"),
        row("Brier score, last 2 minutes only", lambda r: f"{r['phases']['last_2_minutes']['brier']:.4f}"),
    ]
    phases = [head, sep] + [
        row(ph.replace("_", " ").capitalize(), lambda r, ph=ph: f"{r['phases'][ph].get('brier', float('nan')):.4f}")
        for ph in PHASES
    ]
    sanity = [
        head,
        sep,
        row("Final play: mean probability on the winner", lambda r: f"{r['final_play']['mean_prob_on_winner']:.3f}"),
        row("Final play: share above 0.95", lambda r: f"{r['final_play']['share_above_0.95']:.3f}"),
        row("Tipoff: correlation with strength_gap", lambda r: f"{r['tipoff']['corr_with_strength_gap']:.3f}"),
        row("Worst calibration bin (points)", lambda r: f"{r['max_bin_gap'] * 100:.1f}"),
    ]

    base = results.get("logreg", {}).get("brier")
    challengers = {n: results[n]["brier"] for n in names if n != "logreg"}
    beats = [n for n, b in challengers.items() if base is not None and b < base]
    prod = meta.get("production")
    checks = [
        f"- [{'x' if beats else ' '}] XGBoost or the MLP beats the logistic regression baseline on test "
        f"Brier ({', '.join(LABELS[n] for n in beats) or 'neither does'})",
        f"- [{'x' if results.get(prod, {}).get('calibrated_within_5pts') else ' '}] Production model "
        f"({LABELS.get(prod, prod)}) has every calibration bin within 5 points of the diagonal "
        f"(bins with ≥{MIN_BIN_ROWS} plays)",
    ]

    train = meta["split"]["train"]
    test = meta["split"]["test"]
    intro = (
        f"Test season **{test['seasons'][0]}**: {test['games']:,} games, {test['plays']:,} plays. "
        f"Trained on {', '.join(train['seasons'])}: **{train['games']:,} games, {train['plays']:,} plays**. "
        f"Production model (best validation Brier): **{LABELS.get(prod, prod)}**."
    )
    return {"resume": resume, "phases": phases, "sanity": sanity, "checks": checks, "intro": intro}


def write_markdown(results: dict, meta: dict, source: str) -> str:
    s = _sections(results, meta)
    banner = ""
    if source == "synthetic":
        banner = (
            "> **Synthetic data.** These numbers come from the simulated dataset in "
            "`pipeline/synthetic.py`, not real NBA games. They only show the report works.\n\n"
        )
    return "\n".join(
        [
            "# Evaluation report",
            "",
            banner + s["intro"],
            "",
            "## Headline numbers",
            "",
            *s["resume"],
            "",
            "## Acceptance checks",
            "",
            *s["checks"],
            "",
            "## Calibration",
            "",
            "![Calibration plot](calibration.png)",
            "",
            "## Brier score by game phase",
            "",
            *s["phases"],
            "",
            "## Sanity checks",
            "",
            *s["sanity"],
            "",
        ]
    )


def readme_block(results: dict, meta: dict) -> str:
    """The README's results section: numbers, the two model checks, the plot."""
    s = _sections(results, meta)
    return "\n".join(
        [
            s["intro"],
            "",
            *s["resume"],
            "",
            *s["checks"],
            "",
            "<picture>",
            '  <source media="(prefers-color-scheme: dark)" srcset="reports/calibration-dark.png">',
            '  <img alt="Calibration of each model on the test season" src="reports/calibration.png">',
            "</picture>",
            "",
            "Full report, including scores by game phase and sanity checks: [reports/eval.md](reports/eval.md).",
        ]
    )


README_START = "<!-- results:start -->"
README_END = "<!-- results:end -->"


def update_readme(block_md: str, readme=None) -> bool:
    """Replace the text between the results markers. Returns False if they're missing."""
    readme = readme or config.ROOT / "README.md"
    text = readme.read_text()
    if README_START not in text or README_END not in text:
        return False
    block = f"{README_START}\n{block_md}\n{README_END}"
    text = re.sub(re.escape(README_START) + r".*?" + re.escape(README_END), lambda _: block, text, flags=re.S)
    readme.write_text(text)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    meta = load_meta()
    split = split_by_season(load_features())
    test = split.test
    log.info("test season %s: %d games, %d plays", config.TEST_SEASON, test["game_id"].nunique(), len(test))

    results = {}
    for name in meta["models"]:
        results[name], _ = evaluate_model(name, test)
        r = results[name]
        log.info(
            "%-8s brier %.5f logloss %.5f ece %.4f worst-bin %.3f last2 %.5f",
            name, r["brier"], r["log_loss"], r["ece"], r["max_bin_gap"],
            r["phases"]["last_2_minutes"]["brier"],
        )  # fmt: skip

    out = config.REPORTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    source = config.data_source()
    payload = {
        "data_source": source,
        "sample": config.is_sample(),
        "trained_at": meta.get("trained_at"),  # ties this report to one training run (api/modelcard.py)
        "production": meta["production"],
        "split": meta["split"],
        "models": results,
    }
    (out / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n")
    plot_calibration(results, out / "calibration.png")
    plot_calibration(results, out / "calibration-dark.png", dark=True)
    md = write_markdown(results, meta, source)
    (out / "eval.md").write_text(md)
    if source == "nba" and config.is_sample():
        log.info("sample data (make pull-sample): README left alone; the full `make pull` writes the real results")
    elif source == "nba":
        update_readme(readme_block(results, meta))
    log.info("report written to %s", out)


if __name__ == "__main__":
    main()
