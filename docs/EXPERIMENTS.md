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

## E4. A separate end-of-game model (kept, now on the site)

**2026-11-09.** The whole-game models learn close finishes from a sliver of
their data: 12,145 of 1.8 million training plays (0.7%) are from the last 30
seconds of a game within 3 points. So the end gets a model of its own: XGBoost
trained only on plays with 3:00 or less left (141,883 plays), with the same six
inputs and the same constraints as the whole-game XGBoost (E3). It's blended
into the best whole-game model as the clock runs: none of it at 3:00 left, all
of it from 2:00 on, so the chart never jumps.

Settings swept on the validation season
([experiments/e4_endgame_settings.py](experiments/e4_endgame_settings.py)):
tree depth 4 or 6, leaves of 50, 200 or 1,000, with or without E1's
possession × time input. Kept: depth 4, leaves of 50, no extra input (best on
close finishes; the extra input didn't add anything).

| Validation Brier | Overall | Last 2 min | Last 30 s | Last 30 s, within 3 pts |
| --- | --- | --- | --- | --- |
| Baseline | 0.15051 | 0.04617 | 0.05112 | 0.12708 |
| Baseline + end-game model | **0.15042** | **0.04478** | **0.04897** | **0.12152** |

Best validation Brier of the four, so it now serves the site
(`model/artifacts/endgame_xgb.json`, base model recorded inside it).
**Test season (2025-26):** Brier 0.14517 vs the baseline's 0.14524; last 2
minutes 0.0459 vs 0.0471; worst calibration bin 1.7 points.

| Situation | Real games | Baseline | End-game model |
| --- | --- | --- | --- |
| Down 2, 10 s left, home ball | 18% | 5% | 15% |
| Tied, 5 s left, home ball | 67% | 54% | 62% |
| Up 3, 30 s left, away ball | 88% | 94% | 90% |

It mostly learned that a small deficit late isn't hopeless; the ball itself
still counts for less than it should (down 2, 10 s left: 15% with the ball,
10% without; real games 18% and 7%).

## E5. Longer end-game window (not kept)

**2026-11-09.** The explorer's error map still showed misses between 6:00 and
3:00, before the hand-over, so the window was tried longer (validation Brier):

| Window: starts → fully in | Overall | 6:00-3:00 | Last 3 min | Last 30 s | Last 30 s, within 3 pts |
| --- | --- | --- | --- | --- | --- |
| Baseline only | 0.15051 | 0.07963 | 0.04986 | 0.05112 | 0.12708 |
| **3:00 → 2:00 (kept)** | **0.15042** | 0.07963 | 0.04876 | **0.04897** | **0.12152** |
| 5:00 → 4:00 | 0.15044 | 0.07992 | 0.04880 | 0.04901 | 0.12162 |
| 6:00 → 4:00 | 0.15043 | 0.07981 | 0.04878 | 0.04921 | 0.12212 |
| 8:00 → 6:00 | 0.15044 | 0.08003 | 0.04872 | 0.04906 | 0.12173 |
| 12:00 → 10:00 | 0.15051 | 0.08003 | 0.04897 | 0.04954 | 0.12301 |

An end-game model doesn't beat the baseline before 3:00, so the misses there
are mostly noise or need different inputs (timeouts left, the foul bonus).
