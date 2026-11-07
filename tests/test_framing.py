"""PRD framing: a sports analytics product, not a betting tool.

No odds and no gambling language anywhere on the site. This scans everything
the web app renders (web/src, web/index.html) and the README for betting terms.
"""

import re

from pipeline import config

BANNED = re.compile(
    r"\b(odds|bets?|betting|bettors?|wagers?|wagering|gambl\w*|sportsbooks?|moneylines?|parlays?|"
    r"point spreads?|vegas|bookmakers?|bookies?|over/under|handicapp\w*)\b",
    re.IGNORECASE,
)


def site_files():
    web = config.ROOT / "web"
    files = [web / "index.html", config.ROOT / "README.md"]
    files += sorted((web / "src").rglob("*.ts*"))
    files += sorted((web / "src").rglob("*.css"))
    return [f for f in files if f.exists()]


def test_no_gambling_language_on_site():
    hits = []
    for f in site_files():
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if m := BANNED.search(line):
                hits.append(f"{f.relative_to(config.ROOT)}:{n}: {m.group(0)!r} in {line.strip()[:80]}")
    assert not hits, "Betting language found:\n" + "\n".join(hits)


def test_banned_pattern_catches_obvious_cases():
    for phrase in ["Live odds", "place a bet", "Vegas line", "sportsbook", "the point spread"]:
        assert BANNED.search(phrase), phrase
    for ok in ["between", "better", "alphabet", "chance to win", "Gambia"]:
        assert not BANNED.search(ok), ok
