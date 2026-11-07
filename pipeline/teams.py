"""The 30 NBA teams: stats.nba.com team IDs, tricodes and names."""

from __future__ import annotations

TEAMS: list[dict] = [
    {"id": 1610612737, "abbr": "ATL", "city": "Atlanta", "name": "Hawks"},
    {"id": 1610612738, "abbr": "BOS", "city": "Boston", "name": "Celtics"},
    {"id": 1610612751, "abbr": "BKN", "city": "Brooklyn", "name": "Nets"},
    {"id": 1610612766, "abbr": "CHA", "city": "Charlotte", "name": "Hornets"},
    {"id": 1610612741, "abbr": "CHI", "city": "Chicago", "name": "Bulls"},
    {"id": 1610612739, "abbr": "CLE", "city": "Cleveland", "name": "Cavaliers"},
    {"id": 1610612742, "abbr": "DAL", "city": "Dallas", "name": "Mavericks"},
    {"id": 1610612743, "abbr": "DEN", "city": "Denver", "name": "Nuggets"},
    {"id": 1610612765, "abbr": "DET", "city": "Detroit", "name": "Pistons"},
    {"id": 1610612744, "abbr": "GSW", "city": "Golden State", "name": "Warriors"},
    {"id": 1610612745, "abbr": "HOU", "city": "Houston", "name": "Rockets"},
    {"id": 1610612754, "abbr": "IND", "city": "Indiana", "name": "Pacers"},
    {"id": 1610612746, "abbr": "LAC", "city": "LA", "name": "Clippers"},
    {"id": 1610612747, "abbr": "LAL", "city": "Los Angeles", "name": "Lakers"},
    {"id": 1610612763, "abbr": "MEM", "city": "Memphis", "name": "Grizzlies"},
    {"id": 1610612748, "abbr": "MIA", "city": "Miami", "name": "Heat"},
    {"id": 1610612749, "abbr": "MIL", "city": "Milwaukee", "name": "Bucks"},
    {"id": 1610612750, "abbr": "MIN", "city": "Minnesota", "name": "Timberwolves"},
    {"id": 1610612740, "abbr": "NOP", "city": "New Orleans", "name": "Pelicans"},
    {"id": 1610612752, "abbr": "NYK", "city": "New York", "name": "Knicks"},
    {"id": 1610612760, "abbr": "OKC", "city": "Oklahoma City", "name": "Thunder"},
    {"id": 1610612753, "abbr": "ORL", "city": "Orlando", "name": "Magic"},
    {"id": 1610612755, "abbr": "PHI", "city": "Philadelphia", "name": "76ers"},
    {"id": 1610612756, "abbr": "PHX", "city": "Phoenix", "name": "Suns"},
    {"id": 1610612757, "abbr": "POR", "city": "Portland", "name": "Trail Blazers"},
    {"id": 1610612758, "abbr": "SAC", "city": "Sacramento", "name": "Kings"},
    {"id": 1610612759, "abbr": "SAS", "city": "San Antonio", "name": "Spurs"},
    {"id": 1610612761, "abbr": "TOR", "city": "Toronto", "name": "Raptors"},
    {"id": 1610612762, "abbr": "UTA", "city": "Utah", "name": "Jazz"},
    {"id": 1610612764, "abbr": "WAS", "city": "Washington", "name": "Wizards"},
]

BY_ID = {t["id"]: t for t in TEAMS}
BY_ABBR = {t["abbr"]: t for t in TEAMS}


def full_name(team_id: int) -> str:
    t = BY_ID.get(int(team_id))
    return f"{t['city']} {t['name']}" if t else str(team_id)
