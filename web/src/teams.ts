// Team colors (primary, alternate), used for the small two-tone team badges.
// Badges always sit next to the team abbreviation, so identity never rests on color alone.

export const TEAM_COLORS: Record<string, [string, string]> = {
  ATL: ["#E03A3E", "#C1D32F"],
  BOS: ["#007A33", "#BA9653"],
  BKN: ["#2B2B2B", "#A1A1A4"],
  CHA: ["#1D1160", "#00788C"],
  CHI: ["#CE1141", "#2B2B2B"],
  CLE: ["#860038", "#FDBB30"],
  DAL: ["#00538C", "#B8C4CA"],
  DEN: ["#0E2240", "#FEC524"],
  DET: ["#C8102E", "#1D42BA"],
  GSW: ["#1D428A", "#FFC72C"],
  HOU: ["#CE1141", "#9EA2A2"],
  IND: ["#002D62", "#FDBB30"],
  LAC: ["#C8102E", "#1D428A"],
  LAL: ["#552583", "#FDB927"],
  MEM: ["#5D76A9", "#12173F"],
  MIA: ["#98002E", "#F9A01B"],
  MIL: ["#00471B", "#EEE1C6"],
  MIN: ["#236192", "#78BE20"],
  NOP: ["#0C2340", "#C8102E"],
  NYK: ["#006BB6", "#F58426"],
  OKC: ["#007AC1", "#EF3B24"],
  ORL: ["#0077C0", "#C4CED4"],
  PHI: ["#006BB6", "#ED174C"],
  PHX: ["#1D1160", "#E56020"],
  POR: ["#E03A3E", "#2B2B2B"],
  SAC: ["#5A2D81", "#63727A"],
  SAS: ["#8A969C", "#2B2B2B"],
  TOR: ["#CE1141", "#A1A1A4"],
  UTA: ["#3E2680", "#79A3DC"],
  WAS: ["#002B5C", "#E31837"],
};

const FALLBACK: [string, string] = ["#8C8C88", "#5A5A57"];

export const teamColors = (abbr: string): [string, string] => TEAM_COLORS[abbr] ?? FALLBACK;
