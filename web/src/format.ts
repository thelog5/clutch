import type { GameSummary, Play } from "./api";

export const pct = (p: number) => `${Math.round(p * 100)}%`;

/**
 * Signed change in win probability, e.g. "+12.4%". (Strictly percentage points;
 * "pts" would read as game points on a basketball page.)
 */
export function change(delta: number, digits = 1): string {
  const v = delta * 100;
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(digits)}%`;
}

/** Size of a swing, e.g. "45%". */
export const swingSize = (delta: number) => `${Math.abs(delta * 100).toFixed(0)}%`;

export function periodLabel(period: number): string {
  if (period <= 4) return `Q${period}`;
  return period === 5 ? "OT" : `${period - 4}OT`;
}

export function playMoment(p: Pick<Play, "period" | "clock">): string {
  return `${periodLabel(p.period)} ${p.clock}`;
}

export function gameDate(iso?: string): string {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function shortDate(iso?: string): string {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function tipoffTime(utc?: string | null): string {
  if (!utc) return "";
  return new Date(utc).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** The team name without the city, e.g. "Raptors". Falls back to the abbreviation. */
export function nickname(name: string, abbr: string): string {
  const parts = name.trim().split(" ");
  if (parts.length < 2) return abbr;
  if (name.endsWith("Trail Blazers")) return "Trail Blazers";
  return parts[parts.length - 1];
}

export function statusLine(g: GameSummary): string {
  if (g.status === "scheduled") return tipoffTime(g.start_time_utc) || g.status_text || "Scheduled";
  if (g.status === "live") return g.status_text || `${periodLabel(g.period ?? 1)} ${g.clock ?? ""}`;
  return "Final";
}
