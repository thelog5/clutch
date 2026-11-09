"""E6 check: our timeout and team-foul counts vs the NBA's own counts in the play text.

Run from the repo root: PYTHONPATH=. .venv/bin/python docs/experiments/e6_count_check.py
Result (2026-11-09): team fouls match on 99.91% of 173,935 fouls; penalty fouls had 0 fouls to give
before them on 99.99% of 53,642; timeouts used match on 99.99% of 66,992.
"""

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.features import CHARGED_TIMEOUTS, build_features

plays = pd.read_parquet(config.PLAYS_PATH)
f = build_features(plays, {})
at, st, d = f.action_type.fillna("").str.lower(), f.sub_type.fillna("").str.lower(), f.description.fillna("")
home = f.side.eq("h")

# fouls: NBA writes (P<player fouls>.T<team fouls this period>) or (P#.PN) once the team is in the penalty
foul = at.eq("foul")
tnum = d.str.extract(r"\(P\d+\.T(\d+)\)")[0].astype(float)
pn = d.str.contains(r"\(P\d+\.PN\)", regex=True)
own = np.where(home, f.home_team_fouls, f.away_team_fouls)
m = foul & tnum.notna()
print(f"team fouls: {int(m.sum()):,} fouls carry the NBA's count; ours matches on {(own[m] == tnum[m]).mean():.2%}")
print("  mismatches by foul type:", st[m & (own != tnum)].value_counts().head(6).to_dict())
# PN = this foul was a penalty foul -> before it, the team had no fouls to give
prev_h = f.home_fouls_to_give.groupby(f.game_id).shift(1)
prev_v = f.away_fouls_to_give.groupby(f.game_id).shift(1)
same_period = f.period.eq(f.period.groupby(f.game_id).shift(1))
give_before = pd.Series(np.where(home, prev_h, prev_v), index=f.index).where(same_period)
pm = foul & pn & give_before.notna()
print(f"penalty fouls (PN): {int(pm.sum()):,}; we had 0 fouls to give before on {(give_before[pm] == 0).mean():.2%}")

# timeouts: NBA writes (Full N Short M) / (Reg.N Short M) = that team's timeouts used so far
to = at.eq("timeout") & st.isin(CHARGED_TIMEOUTS) & (f.period <= 4)
nums = d.str.extract(r"\((?:Full|Reg\.)\s?(\d+) Short (\d+)\)").astype(float)
used = pd.Series(0, index=f.index)
for side in ("h", "v"):
    t = (at.eq("timeout") & st.isin(CHARGED_TIMEOUTS) & f.side.eq(side) & (f.period <= 4)).astype(int)
    used = used.where(~f.side.eq(side), t.groupby(f.game_id).cumsum())
mm = to & nums[0].notna()
nba = nums[0] + nums[1]
print(f"timeouts: {int(mm.sum()):,} carry the NBA's count; ours matches on {(used[mm] == nba[mm]).mean():.2%}")
diff = (used[mm] - nba[mm]).value_counts().head(5).to_dict()
print("  ours minus NBA:", diff)
left = np.where(home, f.home_timeouts, f.away_timeouts)
late = (f.period == 4) & (f.seconds_left <= 30) & (f.margin.abs() <= 3)
print("timeouts left, close last 30 s:", pd.Series(left[late]).value_counts().sort_index().to_dict())
print(
    "fouls to give, close last 30 s:",
    pd.Series(np.where(home, f.home_fouls_to_give, f.away_fouls_to_give)[late]).value_counts().sort_index().to_dict(),
)
