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

## E2. How good is the possession guess? (check, no model change)

**2026-11-09.** `scripts/check_possession.py` compared the guess with the
NBA's own `possession` field from the live-format feed, for 25 games (5 per
season). The two feeds' action numbers line up (home score agrees on 99.9% of
plays). The NBA's field names the team with the ball *during* a play, so the
guess (who has it *after*) is compared with the NBA's value on the next play:

| | Plays | Guess matches the NBA |
| --- | --- | --- |
| All plays | 12,048 | 83.1% |
| Last 2 minutes | 660 | 87.9% |
| Last 30 s | 200 | 90.0% |
| Last 30 s, within 3 points | 90 | 94.4% |

Right about 9 times in 10 late in games: not wrong enough to explain the
late-game gap, so a second download for the NBA's possession field isn't
worth it for this problem.

## E3. XGBoost was memorizing training games (kept)

**2026-11-09.** XGBoost stopped improving after about 50 trees and scored
worse than the baseline on validation (0.1520 vs 0.1505), which a more
flexible model shouldn't. Cause: `strength_gap` is the same for every play in
a game and nearly unique to it, and a leaf only needed 100 units of weight
(about one game's plays), so trees could single out individual training games
and learn how they ended.

Fixes, each tried alone and then together on the validation season:

| XGBoost, validation Brier | Overall | Last 2 min | Last 30 s | Last 30 s, within 3 pts |
| --- | --- | --- | --- | --- |
| Before | 0.15203 | 0.04572 | 0.05058 | 0.12568 |
| Leaves need 1,000 | 0.15152 | 0.04542 | 0.05034 | 0.12507 |
| Strength rounded to whole points | 0.15152 | 0.04559 | 0.05036 | 0.12509 |
| Strength combines only with time | 0.15184 | 0.04583 | 0.05083 | 0.12621 |
| **All three (kept)** | **0.15089** | **0.04518** | **0.05013** | **0.12450** |
| Logistic regression, for reference | 0.15051 | 0.04620 | 0.05110 | 0.12710 |

Also tried, not kept: rounding strength to 2 points (worse); smaller leaves
(300, 100, 30) once the other two fixes were in (worse); boosting from the
baseline's predictions (0.15038 overall, the only version ahead of the
baseline on validation, but it kept almost none of the late-game gain).

**Result on the test season (2025-26):** XGBoost Brier 0.14426 vs the
baseline's 0.14524, log loss 0.4341 vs 0.4375, worst calibration bin 1.9
points, last 2 minutes 0.0459 vs 0.0471. The site still uses the baseline,
because the production pick is the best *overall* validation Brier.

**Still open:** specific final-possession spots remain too low (down 2 with
the ball, 10 s left: real 18%, models 5-10%; tied with the ball, 5 s left:
real 67%, XGBoost 59%). Few training plays sit in those exact spots, and none
of these changes gave the models enough to learn them.
