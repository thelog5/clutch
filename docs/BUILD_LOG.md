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
| 2026-11-07 04:23 EST | M1 | model/data.py: load features, split by season (train 21-22..23-24 / val 24-25 / test 25-26), assert no game or season shared across splits; config gains ARTIFACTS_DIR/REPORTS_DIR (synthetic runs never touch real artifacts) |
| 2026-11-07 04:24 EST | M2 | model/mlp.py: 2x32 ReLU MLP, BCE-with-logits, Adam + LR plateau + early stopping on val logloss; exports weights+scaler to numpy; verified numpy forward == torch (max diff 6e-8) |
| 2026-11-07 04:34 EST | M3 | model/train.py (logreg baseline, monotone XGBoost w/ early stopping on 24-25, MLP; production model = best val Brier; meta.json) + model/predict.py (torch-free predict(state)/predict_frame for the API) |
| 2026-11-07 04:35 EST | M4 | model/evaluate.py: test-season Brier/logloss, 10-bin calibration + ECE + worst-bin acceptance check, phase breakdown (1H/Q3/Q4/last 2 min/OT), final-play + tipoff sanity checks, light+dark calibration PNG small multiples, eval.md + metrics.json, README results block on real data |
| 2026-11-07 04:36 EST | P9 | pull also fetches 2026-27 finished games for replay only (split never includes it); current-season game list re-fetched each run instead of cached |
| 2026-11-07 04:36 EST | A1 | api/settings.py (env-driven paths, live source, poll interval, replay pacing) + api/series.py (displayable plays with prob/delta, JSON play records, biggest swing) shared by precompute and live |
| 2026-11-07 04:37 EST | A2 | api/precompute.py: score every play with the production model -> series.parquet (zstd, small row groups), games.parquet index with biggest swing + closeness, team_strength.json for live; --seasons/--out for a slim deploy bundle |
| 2026-11-07 04:37 EST | A3 | api/store.py: games index in memory (search by team/season/date/free text, sort by date/biggest swing/closeness), series read per game via Parquet row-group filter + LRU cache |
| 2026-11-07 04:39 EST | M5 | Fixed hang: XGBoost (brew libomp) + torch OpenMP deadlock on macOS -> MLP now trains in a spawned child; stable numpy sigmoid; quiet matplotlib font logs. Synthetic run: all 3 models train in ~16s, report + calibration plot render |
| 2026-11-07 04:40 EST | T2 | tests/test_split.py (acceptance: no test-season game in train; checks split logic, leak detection, real features.parquet and trained model's recorded split) + tests/test_predict.py (up 8 w/ 2 min > up 8 at half, final state ~1, strength_gap raises tipoff prob). 26/26 pass on synthetic |
| 2026-11-07 04:41 EST | A4 | api/live.py: LiveHub with one shared poller per watched game (5s poll, same feature code as training, pushes only new plays, resets on feed corrections, final detection); NBALiveSource (cdn.nba.com via nba_api.live, odds block dropped) and FakeLiveSource (stored games replayed on an accelerated clock in live-feed format); scoreboard probabilities from score/clock |
| 2026-11-07 04:42 EST | A5 | api/main.py (health, meta, /games/today, /games search, /games/{id}, /series, WS replay, WS live) + api/replay.py (game-clock pacing at any speed, pause/play/speed/restart commands). Smoke-tested on synthetic: search, series, swing sort, replay @600x, fake live init |
