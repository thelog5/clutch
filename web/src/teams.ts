// Team colors for the tug-of-war chart, and the rules for picking a legible pair.
//
// Each team has a primary and an alternate color. For a game we want:
//   1. each color readable on the current surface (contrast >= 2.2:1), and
//   2. the two teams clearly different (OKLab distance >= 0.12),
// trying home primary/alt against away primary/alt, then falling back to gray
// for the away side. Team abbreviations label both edges of the chart, so
// identity never rests on color alone.

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

const GRAY = { light: "#8C96A8", dark: "#7C879C" };

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function lin(c: number): number {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function oklab(hex: string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex).map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

export function distance(a: string, b: string): number {
  const [x, y] = [oklab(a), oklab(b)];
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

const MIN_CONTRAST = 2.2;
const MIN_DISTANCE = 0.12;

export function pickColors(home: string, away: string, surface: string, dark: boolean): { home: string; away: string } {
  const fallback = dark ? GRAY.dark : GRAY.light;
  const usable = (abbr: string) =>
    (TEAM_COLORS[abbr] ?? [fallback, fallback]).filter((c) => contrast(c, surface) >= MIN_CONTRAST);
  const homeOpts = usable(home).length ? usable(home) : [fallback];
  const awayOpts = [...usable(away), fallback];
  for (const h of homeOpts) {
    for (const a of awayOpts) {
      if (distance(h, a) >= MIN_DISTANCE) return { home: h, away: a };
    }
  }
  return { home: homeOpts[0], away: fallback };
}
