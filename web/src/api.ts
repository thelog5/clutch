// Typed client for the Clutch API (api/main.py).

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000"; // not "localhost": make api listens on IPv4 only, and localhost can resolve to ::1

export function wsUrl(path: string): string {
  return API_URL.replace(/^http/, "ws") + path;
}

export interface Team {
  id: number;
  abbr: string;
  name: string;
  score: number;
}

export interface Swing {
  delta: number;
  description: string;
  period: number;
}

export interface GameSummary {
  id: string;
  season?: string;
  date?: string;
  status: "scheduled" | "live" | "final";
  status_text?: string;
  period?: number;
  clock?: string;
  start_time_utc?: string | null;
  home: Team;
  away: Team;
  home_win?: boolean;
  biggest_swing?: Swing | null;
  in_doubt?: number | null;
  prob?: number | null;
  replay_available?: boolean;
}

export interface Play {
  i: number;
  period: number;
  clock: string;
  elapsed: number;
  home_score: number;
  away_score: number;
  side: "h" | "v" | "";
  description: string;
  prob: number;
  delta: number;
}

export interface Series {
  game: GameSummary;
  plays: Play[];
  biggest_swing: Play | null;
}

/** The latest NBA day's biggest swings: today's finished games, else yesterday's (api/recent.py). */
export interface RecentSwings {
  label: "today" | "yesterday" | "latest" | null;
  date: string | null;
  games: Series[];
  count: number;
}

export interface Health {
  status: string;
  data_source: "nba" | "synthetic";
  games: number;
  model: string | null;
  live_source: string;
  live_ok: boolean | null;
}

export interface Meta {
  seasons: string[];
  teams: { id: number; abbr: string; name: string }[];
  data_source: "nba" | "synthetic";
}

export interface SplitPart {
  seasons: string[];
  games: number;
  plays: number;
}

export interface CalibrationBin {
  lo: number;
  hi: number;
  n: number;
  mean_pred: number;
  frac_pos: number;
}

export type Phase = "first_half" | "third_quarter" | "fourth_quarter" | "last_2_minutes" | "overtime";

export interface TestScores {
  rows: number;
  brier: number;
  log_loss: number;
  ece: number;
  max_bin_gap: number;
  calibrated_within_5pts: boolean;
  bins: CalibrationBin[];
  phases: Partial<Record<Phase, { rows: number; brier: number; log_loss: number }>>;
  final_play?: { mean_prob_on_winner: number; "share_above_0.95": number };
  tipoff?: { corr_with_strength_gap: number; mean_prob: number; home_win_rate: number };
}

/** GET /model: how the serving model was trained and how it scored on the test season. */
export interface ModelCard {
  data_source: "nba" | "synthetic";
  sample: boolean;
  trained_at: string | null;
  production: string;
  calibrated: boolean;
  features: string[];
  split: { train: SplitPart; val: SplitPart; test: SplitPart } | null;
  xgboost_trees: number | null;
  models: Record<
    string,
    {
      train_seconds: number | null;
      val: { brier: number; log_loss: number } | null;
      test: TestScores | null;
    }
  >;
}

export interface GamesPage {
  total: number;
  games: GameSummary[];
  limit: number;
  offset: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_URL + path, { signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, `Can't reach the Clutch API at ${API_URL}.`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, String(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: (s?: AbortSignal) => get<Health>("/health", s),
  meta: (s?: AbortSignal) => get<Meta>("/meta", s),
  model: (s?: AbortSignal) => get<ModelCard>("/model", s),
  today: (s?: AbortSignal) => get<{ games: GameSummary[]; live_ok: boolean | null }>("/games/today", s),
  games: (params: Record<string, string | number | undefined>, s?: AbortSignal) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
    return get<GamesPage>(`/games?${q}`, s);
  },
  game: (id: string, s?: AbortSignal) => get<GameSummary>(`/games/${encodeURIComponent(id)}`, s),
  series: (id: string, s?: AbortSignal) => get<Series>(`/games/${encodeURIComponent(id)}/series`, s),
  recentSwings: (s?: AbortSignal) => get<RecentSwings>("/swings/recent", s),
};
