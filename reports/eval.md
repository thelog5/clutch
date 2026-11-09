# Evaluation report

Test season **2025-26**: 1,229 games, 621,370 plays. Trained on 2021-22, 2022-23, 2023-24: **3,685 games, 1,800,726 plays**. Production model (best validation Brier): **End-game model**.

## Headline numbers

| Metric | Logistic regression | XGBoost | MLP | End-game model |
| --- | --- | --- | --- | --- |
| Brier score | 0.1452 | 0.1443 | 0.1452 | 0.1452 |
| Log loss | 0.4375 | 0.4340 | 0.4371 | 0.4370 |
| Expected calibration error | 0.0099 | 0.0095 | 0.0126 | 0.0102 |
| Brier score, last 2 minutes only | 0.0471 | 0.0459 | 0.0475 | 0.0459 |

## Acceptance checks

- [x] XGBoost or the MLP beats the logistic regression baseline on test Brier (XGBoost, MLP, End-game model)
- [x] Production model (End-game model) has every calibration bin within 5 points of the diagonal (bins with ≥200 plays)

## Calibration

![Calibration plot](calibration.png)

## Brier score by game phase

| Metric | Logistic regression | XGBoost | MLP | End-game model |
| --- | --- | --- | --- | --- |
| First half | 0.1849 | 0.1834 | 0.1838 | 0.1849 |
| Third quarter | 0.1334 | 0.1330 | 0.1345 | 0.1334 |
| Fourth quarter | 0.0786 | 0.0781 | 0.0794 | 0.0783 |
| Last 2 minutes | 0.0471 | 0.0459 | 0.0475 | 0.0459 |
| Overtime | 0.1410 | 0.1403 | 0.1545 | 0.1413 |

## Sanity checks

| Metric | Logistic regression | XGBoost | MLP | End-game model |
| --- | --- | --- | --- | --- |
| Final play: mean probability on the winner | 1.000 | 0.994 | 0.998 | 0.995 |
| Final play: share above 0.95 | 1.000 | 1.000 | 0.992 | 0.990 |
| Tipoff: correlation with strength_gap | 0.997 | 0.979 | 0.981 | 0.997 |
| Worst calibration bin (points) | 1.6 | 1.9 | 3.3 | 1.7 |
