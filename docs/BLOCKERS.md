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

