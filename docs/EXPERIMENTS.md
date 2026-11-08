# Model experiments

Changes tried on the model, what they were meant to fix, and what the numbers
said. Decisions are made on the validation season (2024-25); the test season
(2025-26) is only for the final report.

## E1. Possession × time input (not kept)

**2026-11-08.** Problem: the models undervalue having the ball in the final
seconds. In real games (2021-22 to 2025-26, regulation only):

| Situation | Home team actually won | Models said |
| --- | --- | --- |
| Down 2, 5-15 s left, home ball | 18% of 187 games | 5-15% |
| Tied, 3-8 s left, home ball | 67% of 109 games | 51-58% |

**Change:** a seventh input, `possession_x_time = (2 * home_possession - 1) / sqrt(seconds_left + 1)`
(0 at 0:00), so the ball counts for more as time runs out, the same way
`margin_x_time` scales the lead. Patch: [experiments/possession_x_time.patch](experiments/possession_x_time.patch).

**Result:** it fixed the tied case for the baseline (54% to 66%), but late-game
accuracy on the validation season didn't improve for any model:

| Validation Brier, last 30 s with the clock running | Before | After |
| --- | --- | --- |
| Logistic regression | 0.0511 | 0.0520 |
| XGBoost | 0.0506 | 0.0505 |
| MLP | 0.0494 | 0.0496 |

(The first version, without the 0:00 cutoff, also made plays at 0:00 worse:
0.0138 to 0.0174.) Overall Brier was unchanged for all three. Reverted.

**Likely cause:** the possession input itself. It's a guess from the last made
shot, final made free throw, rebound or turnover. If the guess is often wrong
late in games (fouls, free throws, jump balls, timeouts), every model learns
that the ball matters less than it does, and no reshaping of the input fixes
that. **Next:** measure the guess against the NBA's own `possession` field
from the live-format feed (`scripts/check_possession.py`). If it's often
wrong, train on the real possession instead, and retry this input on top.
