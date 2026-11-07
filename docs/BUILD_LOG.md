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
