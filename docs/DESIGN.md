# Web design notes

**Subject.** NBA win probability, play by play. **Audience.** Basketball fans and
recruiters skimming a portfolio. **Primary job.** Make a lead's safety visible:
watch the line move and see which play swung it.

## The look

A broadcast scoreboard: a black header bar, white cards on warm light paper,
heavy condensed italic caps for headings and scores, and one accent color,
orange, for everything that is "the model's number": the probability line, the
favored side of a probability bar, the live and replay tags, primary buttons.

## Logo

A basketball (ring, vertical seam, two side arcs) with an orange rising
win-probability line breaking out of it toward the top right. The line is drawn
twice: first wide in the background color, so it cuts cleanly through the ball,
then in orange. `web/src/components/Logo.tsx` draws it with `currentColor` for
the ball and `--logo-knockout` for the cut, so it works on the black header and
on paper. The wordmark is Archivo at its widest (`font-stretch: 125%`), weight
900, italic caps. `web/public/favicon.svg` is the app-icon form: the mark on a
black rounded square.

## Tokens

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| paper | `#F4F4F2` | `#0D0D0E` | page |
| surface | `#FFFFFF` | `#171719` | cards |
| ink | `#111111` | `#F3F3F1` | text |
| ink-2 / ink-3 | `#474744` / `#6E6E6A` | `#C2C2BC` / `#93938D` | secondary text |
| line | `#E2E2DE` | `#2B2B2E` | borders, grid |
| brand | `#F0561D` | `#FF6A2B` | chart line, bars, logo |
| brand-strong | `#D2450E` | same | under white text (4.6:1) |
| brand-ink | `#C2410C` | `#FF8A57` | orange text |
| header | `#0B0B0B` | same | header bar, both modes |

Team colors appear only as small two-tone badges next to the team
abbreviation, so identity never rests on color alone. They never color the
chart.

## Type

One family, Archivo (variable: width 62-125, weight 400-900, italic):

* **Headings** (`.display`): width 62%, weight 850, italic, uppercase.
* **Scores and abbreviations**: width 75%, weight 800, tabular figures.
* **Wordmark**: width 125%, weight 900, italic, uppercase.
* **Body**: width 100%, 400-600.

`tabular-nums` for clocks, scores and the play tables so columns don't jitter
while a replay runs.

## Layout

```
Home
+--------------------------------------------------------------+
| [mark] CLUTCH   Live  Tonight  Past games  How it's built       |
| [ LIVE (2) | NOP 88 PHX 88 Q4 4:18 | MEM 72 TOR 66 Q3 7:14 | ... ]     |
| EVERY POSSESSION CHANGES THE GAME.                            |
| [ WHAT YOU'RE LOOKING AT: an ML model that predicts who wins  |
|   01 learns  02 models compete  03 predicts  04 tested  stack ]|
| / LIVE NOW (2)                                               |
| [ featured: teams | live | win prob bar ]  [ side card ]     |
| [ chart, current play dot ]                [ side card ]     |
| / TONIGHT (3)            / PAST GAMES   [search][season][sort]|
| [ MIL at CLE   8:00 PM ] | Date | Final | Swing | Replay ->  |
+--------------------------------------------------------------+
```

The "What you're looking at" card is for a first-time visitor (often a
recruiter): it says in plain words that this is a machine-learning model, how it
learned, how it was tested, and the stack, with the real counts and calibration
gap from `GET /model`, and links to "How it's built".

When nothing is live, "Live now" becomes "Biggest swings": the three most
dramatic games of the latest finished season, the first with its full chart.

```
Game center
+--------------------------------------------------------------+
| <- Back to games                                             |
| GAME CENTER                                    [Copy link]   |
| [ BOS 104 | NYK 101 home | LIVE Q4 2:14 | win prob bar ]     |
| Overview  Play-by-play                                       |
| [ chart                 ]  [ latest 8 plays, current row   ] |
| [ Play  60x  =====o-------------------  Q1 Q2 Q3 Q4 ]        |
| [ biggest swing card ]                                       |
+--------------------------------------------------------------+
```

The slider and quarter buttons seek the replay stream (`{"cmd": "seek"}`). For
a finished game that isn't replaying, the score bar shows the chance at
tipoff.

```
How it's built
+--------------------------------------------------------------+
| BEHIND THE PROBABILITY.   [Game state] -> [model] -> [Win %]  |
| [ plays learned ] [ games held out ] [ Brier ] [ calib. gap ] |
| / HOW IT'S TRAINED                                           |
| [ train ==================== | validate ===== | test ===== ] |
| [ 01 rows + inputs ]  [ 02 three models, val Brier, time ]  |
| [ 03 validation pick ] [ 04 tested once, then served ]      |
| / HOW IT SCORES                                              |
| [ test table: Brier, log loss, calibration gap, final 2 min ] |
| [ calibration chart ]  [ Brier by game phase + sanity checks ] |
+--------------------------------------------------------------+
```

Every number on it comes from `GET /model`, which reads the trained model's
`meta.json` and the test-season `metrics.json` written by `model.evaluate`
(only when both come from the same training run). The calibration chart is the
serving model's 10 bins against the diagonal, with a ±5-point band; each dot
has a tooltip and the same numbers are in a table. When the API runs on
simulated or sample data, one line under the stats says so.

Max width 1200px; 16px gutters on phones, 28px from 720px up. Two-column grids
collapse to one below 960px.

## Motion

Only what answers the data: the line grows as a replay streams, the current
play dot moves, the probability bar eases to its new split, the live tag
blinks. No entrance animations. `prefers-reduced-motion` turns all of it off
(replay still works).
