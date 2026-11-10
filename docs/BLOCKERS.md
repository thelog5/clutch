# Blockers and things only Logan can do

Things I couldn't do from the build sandbox: network access, accounts, keys,
or anything that needs a real browser or a real game. Each item says exactly
what to run or click. Tick them off as you go.

---

- [x] **B1. Run the real data pull (stats.nba.com).** Done 2026-11-08: 6,289 games, none failed.
  The sandbox wasn't allowed to call stats.nba.com, so everything so far was
  built and tested against a synthetic dataset (see `pipeline/synthetic.py`).
  No metric from that dataset is a real result.
  Run this on your machine and leave it overnight (it resumes if interrupted):
  ```bash
  make setup
  make pull-smoke  # 5 games: confirms stats.nba.com answers from your network
  # Optional quick test first (~25 min): 150 games per season, then
  #   make features train precompute && make api   (and make web)
  # Sample results stay out of the README; the full pull reuses these games.
  make pull-sample
  make pull        # 1-2 hours, cached per game in data/raw/
  make features    # builds data/features.parquet
  make train       # trains all three models + writes the eval report
  make precompute  # writes per-game probability series for the API
  ```

- [x] **B0. GitHub rejected the first push (email privacy).** Your account blocks
  pushes that expose your personal email address. I set **this repo only** to commit
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

- [ ] **B3. Deploy the API and the website on Render** (next to your existing
  site, in the same account). The deploy data is already committed (`api/data/`,
  2,598 games from 2024-25 through 2026-11-09, scored by the end-game model),
  along with `model/artifacts/` and `reports/`. Rerun `make deploy-bundle` and
  commit after `make refresh` to add newer games.
  Step by step (about 15 minutes, most of it waiting for the first build):
  1. Render dashboard → **New** → **Blueprint**. Connect GitHub if asked and
     give Render access to the `clutch` repo (it's private). Pick it, branch
     `main`. Render reads `render.yaml` and lists `clutch-api` (Python, free)
     and `clutch-web` (static site, free). Your existing site isn't touched.
  2. It asks for `CLUTCH_CORS_ORIGINS` and `VITE_API_URL`. Leave both blank
     for now and click **Apply**. The API takes 3-5 minutes to build, the site
     about 1.
  3. Open `clutch-api`, copy its address (top of the page, like
     `https://clutch-api.onrender.com`; Render adds a suffix if the name is
     taken). Check `<that address>/health` shows `"data_source": "nba"` and
     `"model": "endgame"`.
  4. Open `clutch-web` → **Environment** → set `VITE_API_URL` to the API
     address (no trailing slash) → **Save, rebuild, and deploy**.
  5. Copy the site's address from `clutch-web`. Open `clutch-api` →
     **Environment** → set `CLUTCH_CORS_ORIGINS` to the site's address (no
     trailing slash) → **Save** (the API restarts).
  6. Open the site: replay a past game (acceptance criterion: replay works on
     the deployed site), check the Film Room and the footer.

  Cost: $0 on top of your current plan. The free API sleeps after 15 minutes
  with no visitors and takes about a minute to wake. Your existing site is on
  a paid instance, so the account's 750 free hours a month all go to
  `clutch-api`, which is enough to run it all month. To keep it awake, set
  its instance type to Starter ($7/mo) in the dashboard.

- [x] **B4. ~~Deploy the web app on Vercel.~~** Not needed: the website is a
  free Render static site, created by B3. (`web/vercel.json` still works if
  you ever want Vercel instead.)

- [ ] **B5. Test live polling from Render (PRD: first thing on day 2).** Open
  `https://<api-url>/games/today`, then `/health`. If `live_ok` is `false`
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

- [x] **B8. Commit the real results.** Done; the README results are from the full run. `make train` on real data rewrites the
  README's Results section (numbers, model acceptance checks, calibration
  plot) and writes `reports/`. Review it, then commit `README.md`,
  `reports/` and `model/artifacts/`.


- [x] **B9. Remove "Co-Authored-By: Claude" from past commits.** Done 2026-11-10: history rewritten
  (same files, authors and dates; only that line removed) and force-pushed. The steps below are kept for reference.
  Commits from 8444f20 on don't have it; the first 57 on `main` (and the
  older `web-revamp` commits) still do. Removing it rewrites those commits:
  same dates and messages, new commit IDs, and a force push replaces
  GitHub's history. Do it when no other Claude session is working in the
  repo. Ask Claude ("remove the co-author lines"), or:
  ```bash
  git filter-branch --msg-filter 'sed "/^Co-Authored-By: Claude/d" | git stripspace' -- main web-revamp
  git push --force-with-lease origin main
  ```
