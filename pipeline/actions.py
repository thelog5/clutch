"""One canonical play schema shared by historical and live data.

Historical plays come from ``PlayByPlayV3`` (stats.nba.com); live plays come
from the ``liveData`` play-by-play feed (cdn.nba.com). The two use different
field names and action type spellings, so both are normalized here into the
same columns. Feature code only ever sees the canonical form, which keeps
training and live serving on one code path.

Canonical columns
-----------------
game_id, action_number, period, clock, side, action_type, sub_type,
description, score_home, score_away

``side`` is "h" (home), "v" (visitor) or "" (no team, e.g. period start).
``action_type`` uses the V3 spellings: "Made Shot", "Missed Shot",
"Free Throw", "Rebound", "Turnover", "Foul", "Violation", "Substitution",
"Timeout", "Jump Ball", "period", ...
"""

from __future__ import annotations

import re

import pandas as pd

CANONICAL_COLUMNS = [
    "game_id",
    "action_number",
    "period",
    "clock",
    "side",
    "action_type",
    "sub_type",
    "description",
    "score_home",
    "score_away",
]

_CLOCK_RE = re.compile(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")


def clock_to_seconds(clock: str | None) -> float:
    """``"PT11M48.00S"`` -> 708.0. Empty or unparseable clocks return 0."""
    if not clock or not isinstance(clock, str):
        return 0.0
    m = _CLOCK_RE.fullmatch(clock.strip())
    if not m:
        # Old-style "11:48" clocks show up in a few feeds.
        if ":" in clock:
            mins, secs = clock.split(":", 1)
            try:
                return int(mins) * 60 + float(secs)
            except ValueError:
                return 0.0
        return 0.0
    mins = int(m.group(1) or 0)
    secs = float(m.group(2) or 0.0)
    return mins * 60 + secs


def format_clock(seconds: float) -> str:
    """708.0 -> ``"11:48"``; under a minute shows tenths, like the broadcast."""
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"0:{seconds:04.1f}"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _scores(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace("", None), errors="coerce")


def _game_ids(ids: pd.Series) -> pd.Series:
    """Restore leading zeros on numeric NBA IDs ("22100001" -> "0022100001")."""
    ids = ids.astype(str)
    return ids.where(~ids.str.isdigit(), ids.str.zfill(10))


def from_v3(raw: pd.DataFrame, home_team_id: int | None = None) -> pd.DataFrame:
    """Normalize a PlayByPlayV3 frame for one game."""
    df = raw.copy()
    side = df.get("location", pd.Series("", index=df.index)).fillna("").astype(str).str.lower()
    if home_team_id is not None and "teamId" in df:
        # Fill rows where location is blank but the team is known.
        team = pd.to_numeric(df["teamId"], errors="coerce").fillna(0).astype(int)
        missing = (side == "") & (team != 0)
        side = side.mask(missing & (team == home_team_id), "h")
        side = side.mask(missing & (team != home_team_id), "v")

    out = pd.DataFrame(
        {
            "game_id": _game_ids(df["gameId"]),
            "action_number": pd.to_numeric(df["actionNumber"], errors="coerce").astype("Int64"),
            "period": pd.to_numeric(df["period"], errors="coerce").astype("Int64"),
            "clock": df["clock"].fillna("").astype(str),
            "side": side.where(side.isin(["h", "v"]), ""),
            "action_type": df["actionType"].fillna("").astype(str),
            "sub_type": df["subType"].fillna("").astype(str),
            "description": df["description"].fillna("").astype(str),
            "score_home": _scores(df["scoreHome"]),
            "score_away": _scores(df["scoreAway"]),
        }
    )
    return out[CANONICAL_COLUMNS]


# liveData actionType -> V3 actionType
_LIVE_TYPES = {
    "freethrow": "Free Throw",
    "rebound": "Rebound",
    "turnover": "Turnover",
    "foul": "Foul",
    "violation": "Violation",
    "substitution": "Substitution",
    "timeout": "Timeout",
    "jumpball": "Jump Ball",
    "period": "period",
    "game": "game",
    "instantreplay": "Instant Replay",
    "ejection": "Ejection",
    "steal": "Steal",
    "block": "Block",
    "stoppage": "Stoppage",
}


def from_live(actions: list[dict], game_id: str, home_team_id: int) -> pd.DataFrame:
    """Normalize liveData ``game.actions`` for one game."""
    rows = []
    for a in actions:
        live_type = str(a.get("actionType") or "").lower()
        if live_type in ("2pt", "3pt"):
            made = str(a.get("shotResult") or "").lower() == "made"
            action_type = "Made Shot" if made else "Missed Shot"
        else:
            action_type = _LIVE_TYPES.get(live_type, live_type.title())

        team_id = a.get("teamId") or 0
        side = ""
        if team_id:
            side = "h" if int(team_id) == int(home_team_id) else "v"

        description = str(a.get("description") or "")
        if action_type == "Free Throw" and str(a.get("shotResult") or "").lower() == "missed":
            if not description.upper().startswith("MISS"):
                description = "MISS " + description

        rows.append(
            {
                "game_id": str(game_id),
                "action_number": a.get("actionNumber"),
                "period": a.get("period"),
                "clock": a.get("clock") or "",
                "side": side,
                "action_type": action_type,
                "sub_type": str(a.get("subType") or ""),
                "description": description,
                "score_home": a.get("scoreHome"),
                "score_away": a.get("scoreAway"),
            }
        )
    df = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
    df["action_number"] = pd.to_numeric(df["action_number"], errors="coerce").astype("Int64")
    df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
    df["score_home"] = _scores(df["score_home"].astype("object"))
    df["score_away"] = _scores(df["score_away"].astype("object"))
    return df
