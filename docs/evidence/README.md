# Evidence: how the model was tuned

Everything needed to show the original problem, what changed, and whether it
helped. Numbers are saved as CSV/JSON next to every chart, so any chart can be
redrawn. **Start with [COMPARISON.md](COMPARISON.md)** (before/after, generated)
and [../EXPERIMENTS.md](../EXPERIMENTS.md) (what was tried and why).

## Where each piece lives

| You want to show | Look at | What's in it |
| --- | --- | --- |
| **The original failures** | [cases.csv](cases.csv), [runs/R0-original/situations.csv](runs/R0-original/situations.csv), [runs/R0-original/reality.csv](runs/R0-original/reality.csv), [runs/R0-original/explorer.png](runs/R0-original/explorer.png) | 12 real moments (game ID, date, teams, clock, score, possession, the original model's probability, the result, what happened next); fixed situations with real-game rates and game counts; every score × time × possession cell, model vs reality |
| **Training setup** | `runs/*/setup.json` | Seasons, games, plays, inputs, model types, every setting, the commit, and a SHA-256 of each model file |
| **Data split** | [split/train.csv](split/train.csv), [split/validation.csv](split/validation.csv), [split/test.csv](split/test.csv), `tests/test_split.py` | The game IDs in each part (3,685 / 1,230 / 1,229 games); the test that no test game is in training |
| **Baseline results** | [runs/R0-original/metrics.csv](runs/R0-original/metrics.csv), [runs/R0-original/calibration.csv](runs/R0-original/calibration.csv) | Brier and log loss for every model, on the validation and test seasons, for the whole game, last 2 minutes, last 30 seconds and close finishes, with play and game counts |
| **Experiment history** | [../EXPERIMENTS.md](../EXPERIMENTS.md), [../experiments/](../experiments/) | Hypothesis, change, commit, results, kept or not; the sweep scripts and a patch for the one that was reverted |
| **Final comparison** | [COMPARISON.md](COMPARISON.md), [charts/](charts/) | Old and new predictions on the same situations and the same 12 moments, plus aggregate metrics, per version |

## Versions (one folder each in `runs/`)

| Run | Commit | Change |
| --- | --- | --- |
| R0-original | `0a7bf5c` | First full real-data training run (baseline on the site) |
| R1-xgboost-fix | `11184b1` | E3: XGBoost stops memorizing training games |
| R2-endgame | `1e6d2e2` | E4: separate end-of-game model, now on the site |
| R3-timeouts-fouls | patch on `8e1e87b` | E6: timeouts left and fouls to give as inputs (**not kept**: worse on validation) |

Commits are on `main`. A version marked not kept was snapshotted before it was
reverted, so its evidence is still here. Each run folder holds:

| File | What it is |
| --- | --- |
| `setup.json` | How that version was trained, plus the commit and file hashes |
| `metrics.csv` | One row per model × season (validation, test) × game situation: plays, games, Brier, log loss, mean prediction, home win rate |
| `calibration.csv`, `calibration.png` | Test-season calibration, 10 bins per model |
| `situations.csv` | Fixed what-if situations: each model's answer, and its average over the matching real moments next to the real home win rate |
| `cases.csv` | The 12 frozen real moments, scored by each model |
| `reality.csv` | Every score × time × possession cell in 2024-26: real games, real home win rate, each model's average prediction (the data behind the explorer's error map) |
| `explorer.html`, `explorer.png` | The model explorer for that version, and a screenshot |

## Definitions

* **Brier score**: the average of (predicted chance − result)², where the result is 1 if the home team won. Lower is better; always saying 50% scores 0.25.
* **Validation season** (2024-25) is where every decision was made. **Test season** (2025-26) is only for the final grade.
* **Real games** in situations and reality files are 2024-25 and 2025-26, seasons no model trained on. Each game counts once (its plays in the situation are averaged first).
* **Last 2 minutes / last 30 seconds**: regulation only. **Close**: within 3 points. (The README's "last 2 minutes" also includes overtime, so its numbers differ slightly.)
* **Cases** were picked once, with the original model, by a fixed rule: 2025-26, regulation, 0:30 to 0:01 left, within 3 points, possession known; for each game the play where the original model was furthest from the result; the 12 furthest. Upsets happen even with a perfect model. What the cases show is how *confident* the original model was (0.1% for a home team down 3 with the ball and 1.9 seconds left).

## Data problems found on the way

Found when the real data first ran (before R0), each with its own commit:

| Problem | Effect | Fix |
| --- | --- | --- |
| Neutral-site games (Mexico City, Paris, Berlin, London, NBA Cup semifinals) list both teams as "A @ B" | 11 real games thrown away | `e805450`: the team after "@" is home |
| Late instant-replay reviews are logged after the fact with an earlier clock | 16 good games dropped; replays would jump back in time | `1ec8e4b`: plays ordered by game clock |
| macOS treats `data/SYNTHETIC` and `data/synthetic/` as the same name | Real data labeled as simulated | `1ec8e4b`: markers checked as files |
| 2 games' play-by-play stops early (one at halftime) | Final score doesn't match | Dropped by the score check, by design |

## Adding a version

```bash
make train                                   # trains, evaluates, updates README and reports/
.venv/bin/python -m scripts.snapshot R3-<name> --label "E6: <what changed>" --screenshot
PYTHONPATH=. .venv/bin/python docs/evidence/compare.py
```

Then add the run to the table above, write the experiment up in `docs/EXPERIMENTS.md`
(hypothesis, change, commit, results, kept), and commit. To save a version that
isn't kept, snapshot it before reverting.
