# Build log

Every block of work gets one line here, written by `scripts/checkpoint.sh` in
the same commit that delivers it. Times are local (America/New_York). To find
the exact commit for a line, run `git log --grep "Block: <id>"`.

**Block legend**

| Prefix | Area |
| --- | --- |
| S | Scaffolding, tooling, docs |
| P | `pipeline/` (data pull, features, Parquet) |
| M | `model/` (training, evaluation, `predict`) |
| A | `api/` (FastAPI, precompute, WebSockets) |
| W | `web/` (React app) |
| T | Tests |
| D | Deploy config |

| When | Block | What was done |
| --- | --- | --- |
| 2026-11-07 04:14 EST | S1 | Repo scaffold: README, .gitignore, build log + checkpoint script, QUESTIONS.md, BLOCKERS.md (B1: data pull blocked in sandbox) |
| 2026-11-07 04:16 EST | S2 | pyproject.toml with pinned-floor deps (train/dev extras), Makefile targets for pull/features/train/precompute/synthetic/api/web/test |
| 2026-11-07 04:17 EST | P1 | pipeline/config.py: data paths (CLUTCH_DATA_DIR override), season split 21-22..23-24 train / 24-25 val / 25-26 test, prior season 20-21 for strength blend |
| 2026-11-07 04:18 EST | P2 | pipeline/games.py: LeagueGameFinder per season (cached Parquet, retry/backoff), collapse home/away team rows into one game row with home_win |
| 2026-11-07 04:18 EST | P3 | pipeline/actions.py: one canonical play schema; normalizers for PlayByPlayV3 (historical) and liveData (live) so training and live serving share feature code; clock parsing/formatting |
| 2026-11-07 04:18 EST | P4 | pipeline/pbp.py + pipeline/pull.py: per-game cached PlayByPlayV3 pull with retries, jittered delay, ETA logging, failed.txt for resume; combine into canonical plays.parquet; --limit smoke-test flag |
| 2026-11-07 04:19 EST | P5 | pipeline/strength.py: season-to-date point differential per game using only earlier games; blend toward last season's differential for first 10 games; current_strength() for live games |
| 2026-11-07 04:19 EST | P6 | pipeline/features.py: vectorized per-play features (margin, seconds_left, is_ot, home_possession heuristic, strength_gap, margin_x_time) + home_win label; final-score check vs box score; writes features.parquet |
| 2026-11-07 04:20 EST | P7 | pipeline/teams.py: 30 teams with stats.nba.com IDs, tricodes, city + nickname |
| 2026-11-07 04:22 EST | P8 | pipeline/synthetic.py: possession-level game simulator (team strength, home edge, OREBs, FTs, OT, late-game fouling/clock milking) writing raw V3-shaped per-game Parquet + SYNTHETIC marker; verified features build on it (317 games / 120k plays smoke run) |
| 2026-11-07 04:22 EST | T1 | tests/test_features.py + tests/test_strength.py (15 tests): clock parsing, seconds_left in reg/OT, score ffill, margin_x_time, possession heuristic, live-feed normalization, strength_gap uses only earlier games + last-season blend |
