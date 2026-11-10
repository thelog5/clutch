// What the site shows before the API answers (scripts/web_snapshot.py).
// The free API can take up to a minute to wake, so the site ships with the
// latest day's biggest swings, this season's biggest swings, the first page of
// past games, the seasons and the model card, and swaps in fresh data as each
// request comes back. Saved games carry their full series, so they open
// without the API.
import saved from "./data/snapshot.json";
import type { GameSummary, GamesPage, Meta, ModelCard, RecentSwings, Series } from "./api";

export interface Snapshot {
  saved_at: string;
  meta: Meta;
  model: ModelCard;
  swings: RecentSwings;
  season_swings: { season: string; games: Series[] };
  past: GamesPage;
}

export const SNAPSHOT = saved as unknown as Snapshot;

const SAVED = new Map<string, Series>([...SNAPSHOT.swings.games, ...SNAPSHOT.season_swings.games].map((s) => [s.game.id, s]));

/** A game saved with its full series, so its page opens before the API is up. */
export function savedSeries(id: string): Series | undefined {
  return SAVED.get(id);
}

export function savedGame(id: string): GameSummary | undefined {
  const s = SAVED.get(id);
  return s && { ...s.game, replay_available: true };
}

/** Today's date on the NBA's calendar (Eastern time), as YYYY-MM-DD. */
function nbaToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
}

/** "today", "yesterday" or "latest" for a saved day, as of now rather than when it was saved. */
export function dayLabel(date: string | null): RecentSwings["label"] {
  if (!date) return null;
  const today = nbaToday();
  const d = new Date(`${today}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return date === today ? "today" : date === d.toISOString().slice(0, 10) ? "yesterday" : "latest";
}
