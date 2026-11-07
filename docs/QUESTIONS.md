# Questions for Logan

Decisions I couldn't make from the PRD alone. Where I needed an answer to keep
moving, I used the **default** listed and built around it, so changing it later
is a small edit. Write your answer under each question and I'll apply it.

---

### Q1. Chart: home team's probability or the favored team's?
PRD open question. **Default used:** the chart and big number always show the
**home** team. The game page header says which team that is, and the big number
also shows the away team's complement in small text.
Switching to "favored team" means flipping the series whenever the home team is
below 50% at tipoff, which only touches the web layer.

> Answer:

### Q2. Is replay alone a strong enough public demo if live polling gets blocked on Render?
PRD open question. **Default used:** yes. The deployed site leads with replay,
and live mode turns on automatically only if the backend can reach the NBA live
feed (`/health` reports `live_ok`).

> Answer:

### Q3. Include playoff games?
**Default used:** regular season only, matching the PRD's ~1,230 games per
season. Adding playoffs (and play-in) is one line in `pipeline/config.py`
(`SEASON_TYPES`). Options: (a) keep regular season only, (b) add playoffs for
replay only, (c) add playoffs to training too.

> Answer:

### Q4. Which model should the site use?
**Default used:** whichever model has the best Brier score on the validation
season (2024-25) is picked automatically at training time and used for replay
and live. On synthetic data that was the MLP. Would you rather pin a specific
model (e.g. always XGBoost, since it's the headline result)?

> Answer:

### Q5. If calibration misses the 5-point target, add a calibration layer?
The acceptance check needs every calibration bin within 5 points of the
diagonal. If the real models miss it, the standard fix is isotonic
calibration fit on the validation season. **Default used:** built as an
opt-in flag (`python -m model.train --calibrate`), off unless you say so,
so the headline numbers are the raw models. Use it if needed?

> Answer:

### Q6. How should the replay data reach Render?
The deployed API needs the precomputed series for the last two seasons plus
this season (estimated 20-30 MB of Parquet). **Default used:**
`make deploy-bundle` writes it to `api/data/` and it gets committed, so Render
just deploys the repo. Alternatives: attach it to a GitHub Release and
download it in the Render build step, or use Git LFS. Fine to commit it?

> Answer:

### Q7. Which game should the home page feature?
**Default used:** the game with the single biggest swing in the most recent
finished season (usually a buzzer-beater), shown with its full chart and a
"Replay this game at 60x" button. Alternatives: the closest game, a game you
pick by ID, or a different game each day.

> Answer:

### Q8. Team colors in the chart: OK?
The chart fills above 50% in the home team's color and below in the away
team's (no logos, team abbreviations label both edges). It gives every game
its own look. If you'd rather keep it brand-neutral, it switches to two fixed
colors in `web/src/teams.ts`.

> Answer:

### Q9. Site address and names
What should the Vercel project / domain be (e.g. `clutch-nba.vercel.app`)? I
left `CLUTCH_CORS_ORIGINS` for you to set once you know it.

> Answer:

