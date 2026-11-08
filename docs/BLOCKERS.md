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

- [ ] **B3. Deploy the API and the website on Render** (next to your existing
  site, in the same account). After B1:
  ```bash
  make deploy-bundle                 # writes api/data/ (last two seasons + current)
  # model/artifacts and reports/ hold the trained model and its test-season
  # numbers; "How it's built" on the site reads both through GET /model.
  git add api/data model/artifacts reports && git commit -m "data: deploy bundle" && git push
  ```
  1. In Render: **New > Blueprint**, pick this repo. It reads `render.yaml`
     and creates two services, `clutch-api` (free instance) and `clutch-web`
     (static site, free). Your existing site isn't touched.
  2. It asks for `VITE_API_URL`. Render names the API
     `https://clutch-api.onrender.com`, or adds a suffix if that name is
     taken, so leave it blank for now if you're not sure.
  3. Once both exist, copy the API's URL from the `clutch-api` page, paste
     it as `VITE_API_URL` on `clutch-web` (Environment), and choose **Save,
     rebuild, and deploy**. The URL is baked in when the site builds.
  4. Check `https://<api-url>/health` shows `"data_source": "nba"`, then open
     the `clutch-web` URL and replay a game.

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

- [ ] **B8. Commit the real results.** `make train` on real data rewrites the
  README's Results section (numbers, model acceptance checks, calibration
  plot) and writes `reports/`. Review it, then commit `README.md`,
  `reports/` and `model/artifacts/`.


- [ ] **B9. (Later) Remove "Co-Authored-By: Claude" from past commits.**
  Commits from 07fceb3 on don't have it; the first 57 on `main` (and the
  older `web-revamp` commits) still do. Removing it rewrites those commits:
  same dates and messages, new commit IDs, and a force push replaces
  GitHub's history. Do it when no other Claude session is working in the
  repo. Ask Claude ("remove the co-author lines"), or:
  ```bash
  git filter-branch --msg-filter 'sed "/^Co-Authored-By: Claude/d" | git stripspace' -- main web-revamp
  git push --force-with-lease origin main
  ```
