# Blockers and things only Logan can do

Things I couldn't do from the build sandbox: network access, accounts, keys,
or anything that needs a real browser or a real game. Each item says exactly
what to run or click. Tick them off as you go.

---

- [ ] **B1. Run the real data pull (stats.nba.com).**
  The sandbox wasn't allowed to call stats.nba.com, so everything so far was
  built and tested against a synthetic dataset (see `pipeline/synthetic.py`).
  No metric from that dataset is a real result.
  Run this on your machine and leave it overnight (it resumes if interrupted):
  ```bash
  make setup
  make pull-smoke  # 5 games: confirms stats.nba.com answers from your network
  make pull        # 1-2 hours, cached per game in data/raw/
  make features    # builds data/features.parquet
  make train       # trains all three models + writes the eval report
  make precompute  # writes per-game probability series for the API
  ```

- [x] **B0. GitHub rejected the first push (email privacy).** Your account blocks
  pushes that expose `your personal email address`. I set **this repo only** to commit
  as `170454143+thelog5@users.noreply.github.com` (`git config user.email`,
  local to `clutch/`). Your global git config is untouched. Nothing to do
  unless you'd rather commit with a different address.

- [ ] **B2. Turn on CI (needs a GitHub token scope I don't have).** GitHub
  refused the push of `.github/workflows/ci.yml` because the `gh` token lacks
  the `workflow` scope. The workflow is parked at `ci/github-actions.yml`
  (lint + tests + web build). To enable it:
  ```bash
  gh auth refresh -h github.com -s workflow
  mkdir -p .github/workflows && git mv ci/github-actions.yml .github/workflows/ci.yml
  git commit -m "ci: enable GitHub Actions" && git push
  ```

- [ ] **B3. Deploy the API on Render.** After B1:
  ```bash
  make deploy-bundle                 # writes api/data/ (last two seasons + current)
  git add api/data model/artifacts && git commit -m "data: deploy bundle" && git push
  ```
  Then in Render: **New > Blueprint**, pick this repo (it reads `render.yaml`).
  Set `CLUTCH_CORS_ORIGINS` to the Vercel URL from B4. Check
  `https://<render-url>/health` shows `"data_source": "nba"`.

- [ ] **B4. Deploy the web app on Vercel.** Import the repo, set **Root
  Directory** to `web`, and add the env var `VITE_API_URL=https://<render-url>`.
  `web/vercel.json` handles the build and SPA routing.

- [ ] **B5. Test live polling from Render (PRD: first thing on day 2).** Open
  `https://<render-url>/games/today`, then `/health`. If `live_ok` is `false`
  and `live_error` looks like a block or timeout, cdn.nba.com is refusing
  Render's IP: set `CLUTCH_LIVE_SOURCE=off` on Render (replay stays the public
  demo, per the PRD fallback) and run live mode locally instead.

- [ ] **B6. Watch one real game in live mode (acceptance criterion).** I
  couldn't reach the NBA live feed from the sandbox, so live mode is only
  tested against recorded games played back on a fast clock
  (`make api-fake`) and unit tests. During a real game:
  ```bash
  make api    # real live feed
  make web    # open http://localhost:5173, click tonight's game
  ```
  Confirm new plays show up within about 15 seconds of the broadcast.

- [ ] **B7. Record the demo GIF (acceptance criterion).** Pick a close game
  (Past games, sort by "Closest"), open it with `?replay=60`, and record the
  chart through to the biggest swing card (macOS: Cmd+Shift+5, then convert
  with `ffmpeg -i in.mov -vf "fps=15,scale=960:-1" docs/demo.gif`). Then
  uncomment the GIF line near the top of the README.

- [ ] **B8. Show the calibration plot in the README.** After `make train` on
  real data, uncomment the `<picture>` block under Results in the README
  (it points at `reports/calibration.png` and the dark variant) and commit
  `reports/`.

