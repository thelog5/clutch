---
title: My model gave Detroit 0.1%. Detroit won.
date: 2026-11-10
summary: What a bad call in the last two seconds taught me about where the model was blind, and the six things I tried to fix it.
draft: true
---

> **Draft.** Only you see this (drafts show when you run the site locally, never on the deployed site).
> Everything below is a skeleton with the real numbers. Rewrite it in your own words, then change
> `draft: true` to `draft: false` at the top. Delete these notes when you're done.

## The call

November 10, 2025. Washington at Detroit, 1.9 seconds left, Detroit down 3 with the ball. My model put
Detroit's chance to win at **0.1%**. Jenkins hit a three with 1.3 seconds left, Detroit won 137-135 in
overtime.

> Write: what you thought when you saw this. Upsets happen even with a perfect model; the problem wasn't
> that Detroit won, it was how *sure* the model was.

## Was it one bad call or a pattern?

I froze the original model's 12 worst calls in close finishes of the test season and checked whole
situations against real games, not just single plays:

| Situation | Real games (2024-26) | Home team won | Original model |
| --- | --- | --- | --- |
| Down 2, 10 s left, home ball | 82 | 18% | 5% |
| Tied, 5 s left, home ball | 46 | 63% | 54% |
| Down 3, 15 s left, home ball | 68 | 9% | 3% |

![The model on the site vs real games, by situation](/film-room/situations_vs_real.png)

> Write: why the baseline couldn't see it. Its weight for "who has the ball" was 0.04, against 5.1 for
> "lead scaled by time". For most of a game the ball is worth about a point, so it learned the ball
> hardly matters, then carried that into the last seconds.

## What I tried

> Write a sentence or two on each, in your words. The full numbers are in `docs/EXPERIMENTS.md`.

1. **An input that makes the ball count more as time runs out.** Fixed the tied case, didn't help on the
   validation season. Reverted.
2. **Checked the possession guess against the NBA's own data.** Right 9 times in 10 in the last 30
   seconds, so that wasn't it.
3. **Found XGBoost memorizing games.** Team strength is one number per game, nearly unique, and the trees
   were using it to look up how training games ended. Rounding it and limiting what it combines with
   fixed it, and XGBoost finally beat the baseline (0.1443 vs 0.1452 Brier on the test season).
4. **Gave the last 3 minutes their own model.** Close finishes are 0.7% of the training plays. A model
   trained only on the end, blended in from 3:00 to 2:00, cut the error in close finishes by 5%.
5. **Started that model earlier.** No better before 3:00. Kept 3:00.
6. **Added timeouts and fouls to give.** Counted them to 99.9% agreement with the NBA's own counts, and
   they didn't help: in real games they barely change the result in these spots.

![How much better the model on the site got, by situation](/film-room/brier_change_by_situation.png)

## Bugs the real data found first

> Write: these are good "it worked on fake data" stories.

* Neutral-site games (Mexico City, Paris, the NBA Cup in Las Vegas) list both teams as "away": 11 real
  games thrown out until I read the home team from after the "@".
* Late instant-replay reviews get logged after the fact with an earlier clock, so they looked like the
  last play of the game: 16 good games dropped.
* My Mac treats `SYNTHETIC` and `synthetic` as the same name, so real data got labeled as fake.

## Where it stands

Detroit, down 3 with the ball and 1.9 seconds left: 0.1% then, 1.4% now.

> Write: what's still wrong (the ball still counts a little too little), and what you'd try next.
