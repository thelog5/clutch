"""Before/after comparison across every saved model version, from the numbers alone.

    PYTHONPATH=. .venv/bin/python docs/evidence/compare.py

Reads docs/evidence/runs/*/ (written by scripts/snapshot.py) and writes
docs/evidence/COMPARISON.md and the charts in docs/evidence/charts/.
Rerun after every new snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = sorted(p for p in (HERE / "runs").iterdir() if (p / "setup.json").exists())
CHARTS = HERE / "charts"
SEGMENTS = ["whole game", "first half", "fourth quarter", "last 2 minutes", "last 30 seconds",
            "close, last 2 minutes", "close, last 30 seconds"]  # fmt: skip
LABELS = {"logreg": "Logistic regression", "xgboost": "XGBoost", "mlp": "Neural net", "endgame": "End-game model"}
# One blue ramp, light to dark: versions are an ordered sequence, not categories.
RAMP = ["#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"


def load():
    setups, metrics, situations, cases = [], [], [], []
    for r in RUNS:
        s = json.loads((r / "setup.json").read_text())
        if not s.get("kept", True):
            s["run"] += " (not kept)"
        setups.append(s)
        metrics.append(pd.read_csv(r / "metrics.csv").assign(run=s["run"]))
        situations.append(pd.read_csv(r / "situations.csv").assign(run=s["run"], production=s["production"]))
        if (r / "cases.csv").exists():
            cases.append(pd.read_csv(r / "cases.csv", dtype={"game_id": str}).assign(run=s["run"],
                                                                                    production=s["production"]))
    return setups, pd.concat(metrics), pd.concat(situations), (pd.concat(cases) if cases else None)


def pct(v):
    return f"{v * 100:.1f}%"


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_brier_change(setups, metrics):
    """Production model's test Brier change vs the original version, per game situation."""
    base_run = setups[0]
    prod = {s["run"]: s["production"] for s in setups}
    test = metrics[metrics["season_role"] == "test"]
    base = test[(test["run"] == base_run["run"]) & (test["model"] == base_run["production"])].set_index("segment")
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=SURFACE)
    style(ax)
    later = setups[1:]
    h = 0.8 / max(1, len(later))
    lows = [0.0]
    for i, s in enumerate(later):
        cur = test[(test["run"] == s["run"]) & (test["model"] == prod[s["run"]])].set_index("segment")
        change = [(cur.loc[seg, "brier"] / base.loc[seg, "brier"] - 1) * 100 for seg in SEGMENTS]
        ys = [k + (i - (len(later) - 1) / 2) * h for k in range(len(SEGMENTS))]
        ax.barh(ys, change, height=h * 0.85, color=RAMP[min(i + 2, len(RAMP) - 1)],
                label=f"{s['run']} ({LABELS.get(prod[s['run']], prod[s['run']])})")  # fmt: skip
        for y, c in zip(ys, change, strict=True):
            if abs(c) >= 0.05:  # a version that kept the same model on the site has nothing to label
                ax.text(c + (0.08 if c >= 0 else -0.08), y, f"{c:+.1f}%", va="center",
                        ha="left" if c >= 0 else "right", fontsize=8, color=INK2)  # fmt: skip
        lows.append(min(change))
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlim(min(lows) * 1.3 - 0.3, 0.6)
    ax.set_yticks(range(len(SEGMENTS)), [f"{s}\n({int(base.loc[s, 'games'])} games)" for s in SEGMENTS])
    ax.invert_yaxis()
    ax.set_xlabel("Change in test-season Brier score vs the original (negative = better)", color=INK2, fontsize=9)
    fig.suptitle(f"Model on the site vs the original ({base_run['run']}), test season",
                 x=0.01, ha="left", color=INK, fontsize=11, fontweight="bold")  # fmt: skip
    fig.legend(frameon=False, fontsize=8.5, loc="lower center", ncol=len(later), bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    path = CHARTS / "brier_change_by_situation.png"
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def chart_situations(setups, situations):
    """Each version's model on the site vs how often real games went the home team's way."""
    names = list(dict.fromkeys(situations["situation"]))
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(names) + 1.4), facecolor=SURFACE)
    style(ax)
    for k, name in enumerate(names):
        rows = situations[situations["situation"] == name]
        real = rows["real_home_win_rate"].iloc[0]
        vals = [rows.loc[rows["run"] == s["run"], f"avg_pred_on_real_{s['production']}"].iloc[0] for s in setups]
        ax.plot([min(vals + [real]) * 100, max(vals + [real]) * 100], [k, k], color=GRID, linewidth=1, zorder=1)
        for i, (s, v) in enumerate(zip(setups, vals, strict=True)):
            dy = (i - (len(setups) - 1) / 2) * 0.13  # versions that share a model would otherwise hide each other
            ax.scatter(v * 100, k + dy, s=46, color=RAMP[min(i * 2, len(RAMP) - 1)], edgecolor=SURFACE, linewidth=1.2,
                       zorder=3, label=s["run"] if k == 0 else None)  # fmt: skip
        ax.scatter(real * 100, k, s=70, facecolor=SURFACE, edgecolor=INK, linewidth=1.8, zorder=4,
                   label="Real games" if k == 0 else None)  # fmt: skip
    games = {n: situations.loc[situations["situation"] == n, "real_games"].iloc[0] for n in names}
    ax.set_yticks(range(len(names)), [f"{n} ({games[n]} games)" for n in names])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Home team's chance to win (%), averaged over the real moments", color=INK2, fontsize=9)
    ax.set_title("Model on the site vs real games, 2024-25 and 2025-26", loc="left", color=INK, fontsize=11,
                 fontweight="bold")  # fmt: skip
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.tight_layout()
    path = CHARTS / "situations_vs_real.png"
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return path


def markdown(setups, metrics, situations, cases, charts) -> str:
    test = metrics[metrics["season_role"] == "test"]
    val = metrics[metrics["season_role"] == "validation"]
    out = ["# Before and after", "",
           "Generated by `docs/evidence/compare.py` from the numbers in `docs/evidence/runs/`. "
           "Don't edit by hand; rerun the script.", "",
           "## Versions", "", "| Run | What changed | Commit | Model on the site | Trained on |",
           "| --- | --- | --- | --- | --- |"]  # fmt: skip
    for s in setups:
        tr = s["split"]["train"]
        out.append(f"| {s['run']} | {s['label']} | `{s['commit']}` | {LABELS.get(s['production'], s['production'])} "
                   f"| {', '.join(tr['seasons'])}: {tr['games']:,} games, {tr['plays']:,} plays |")  # fmt: skip

    out += ["", "## Model on the site, test season", "",
            "A version marked *not kept* was tried and reverted; its column shows what it would have served.", "",
            "Brier score (lower is better). Regulation only for the late-game rows; \"close\" = within 3 points.", "",
            "| Situation | Plays | Games | " + " | ".join(s["run"] for s in setups) + " |",
            "| --- | --- | --- | " + " | ".join("---" for _ in setups) + " |"]  # fmt: skip
    for seg in SEGMENTS:
        cells, first = [], None
        for s in setups:
            r = test[(test["run"] == s["run"]) & (test["model"] == s["production"]) & (test["segment"] == seg)].iloc[0]
            first = first if first is not None else r
            cells.append(f"{r['brier']:.4f}")
        out.append(f"| {seg} | {first['plays']:,} | {first['games']:,} | " + " | ".join(cells) + " |")

    out += ["", "## Every model, close finishes (last 30 seconds, within 3 points)", "",
            "| Run | Model | Validation Brier | Test Brier | Test games |",
            "| --- | --- | --- | --- | --- |"]  # fmt: skip
    seg = "close, last 30 seconds"
    for s in setups:
        for m in s["models"]:
            v = val[(val["run"] == s["run"]) & (val["model"] == m) & (val["segment"] == seg)].iloc[0]
            t = test[(test["run"] == s["run"]) & (test["model"] == m) & (test["segment"] == seg)].iloc[0]
            tag = " (on the site)" if m == s["production"] else ""
            out.append(f"| {s['run']} | {LABELS.get(m, m)}{tag} | {v['brier']:.4f} | {t['brier']:.4f} | {t['games']} |")

    out += ["", "## Situations", "",
            "Real games: 2024-25 and 2025-26 (never trained on), each game counted once. Model columns are the model "
            "on the site, averaged over those same real moments.", "",
            "| Situation | Real games | Home won | " + " | ".join(s["run"] for s in setups) + " |",
            "| --- | --- | --- | " + " | ".join("---" for _ in setups) + " |"]  # fmt: skip
    for name in dict.fromkeys(situations["situation"]):
        rows = situations[situations["situation"] == name]
        first = rows.iloc[0]
        cells = [pct(rows.loc[rows["run"] == s["run"], f"avg_pred_on_real_{s['production']}"].iloc[0]) for s in setups]
        head = f"| {name} | {first['real_games']} | {pct(first['real_home_win_rate'])} | "
        out.append(head + " | ".join(cells) + " |")

    if cases is not None:
        frozen = pd.read_csv(HERE / "cases.csv", dtype={"game_id": str}).set_index("case")
        out += ["", "## Real game moments", "",
                "Frozen in `cases.csv`: the original model's 12 worst calls in close finishes of 2025-26. "
                "Upsets happen even with a perfect model; what matters is how confident the model was.", "",
                "| Case | Game | Moment | Result | " + " | ".join(s["run"] for s in setups) + " |",
                "| --- | --- | --- | --- | " + " | ".join("---" for _ in setups) + " |"]  # fmt: skip
        for case, f in frozen.iterrows():
            cells = []
            for s in setups:
                c = cases[(cases["run"] == s["run"]) & (cases["case"] == case)]
                cells.append(pct(c[f"pred_{s['production']}"].iloc[0]) if len(c) else "")
            out.append(f"| {case} | {f['date']} {f['matchup']} (`{f['game_id']}`) | {f['clock']}, {f['situation']} "
                       f"| {f['result']} | " + " | ".join(cells) + " |")  # fmt: skip

    out += ["", "## Charts", ""] + [f"![{p.stem}](charts/{p.name})" for p in charts] + [""]
    return "\n".join(out)


def main() -> None:
    CHARTS.mkdir(exist_ok=True)
    setups, metrics, situations, cases = load()
    charts = [chart_brier_change(setups, metrics), chart_situations(setups, situations)]
    (HERE / "COMPARISON.md").write_text(markdown(setups, metrics, situations, cases, charts))
    print(f"{len(setups)} versions -> {HERE / 'COMPARISON.md'}")


if __name__ == "__main__":
    main()
