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

