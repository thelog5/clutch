# Web design notes

**Subject.** NBA win probability, play by play. **Audience.** Basketball fans and
recruiters skimming a portfolio. **Primary job.** Make a lead's safety visible:
watch the line move and see which play swung it.

## The one bold thing

The probability chart is a tug-of-war between the two teams. One line (home
win probability), filled toward the 50% line: **above 50% in the home team's
color, below in the away team's**. Every game page takes its identity from the
two real teams playing. Everything around the chart stays quiet.

Identity is never color alone: the top and bottom edges of the chart are
labeled with the team abbreviations, and the big number names the team.
When the two team colors are too close (or too dark for the surface), the away
team switches to its alternate color, then to neutral gray.

## Tokens

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| paper | `#F3F5F8` | `#0E1526` | page |
| surface | `#FFFFFF` | `#151E33` | chart + panels |
| ink | `#14213D` | `#E8ECF4` | text, primary buttons |
| ink-2 | `#4A5878` | `#A9B4CA` | secondary text |
| line | `#D5DBE5` | `#26314A` | dividers, grid |
| ball | `#E8702A` | `#F08A4B` | current-play marker only |

Cool paper and deep navy, not warm cream and not near-black: an arena at
night in dark mode, a printed stat sheet in light mode.

## Type

* **Big Shoulders Display** (700-800): the probability number, team names,
  scores. Condensed, scoreboard character.
* **Archivo** (400-600): everything else. `tabular-nums` for clocks, scores and
  the play feed so columns don't jitter while a replay runs.

Sentence case everywhere. No all-caps eyebrows, no arrows on buttons, no
middle-dot meta strings.

## Layout

```
Home
+--------------------------------------------------------------+
| Clutch                                    Tonight  Past games |
|                                                              |
| Up 8 with two minutes left isn't up 8 at halftime.           |
| [ featured close game: full chart, team-colored ]            |
| [Replay at 60x]                                              |
|                                                              |
| Tonight                                                      |
|  BOS @ TOR   Q3 5:12   66-70   [===TOR 64%====|---]         |
|                                                              |
| Past games  [team v] [season v] [search...] [sort v]          |
|  Mar 7  TOR 133 at DET 107   swing 34 pts   [Replay]          |
+--------------------------------------------------------------+

Game
+--------------------------------------------------------------+
| All games                                                    |
| Toronto Raptors 112        Boston Celtics 108      Final     |
|  73%  Toronto's chance to win            Q4 2:31             |
| [ chart: quarters shaded, 50% dashed, swing marked ]         |
| [Pause] [1x 10x 60x] [Restart] [Show full game] [Copy link]  |
| Biggest swing: +34 points, Q4 0:03, "TOR #7 3PT Jump Shot"   |
| Play by play (latest first, change per play)                 |
+--------------------------------------------------------------+
```

Left aligned throughout. Single column, max width ~1040px, 16px gutters on
phones.

## Motion

Only what answers the data: the line grows as a replay streams, the current
play dot moves, the big number updates. No entrance animations. Respect
`prefers-reduced-motion` (replay still works; nothing eases).
