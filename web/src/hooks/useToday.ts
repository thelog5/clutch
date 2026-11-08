import { useEffect, useState } from "react";
import { api } from "../api";
import { useAsync } from "./useAsync";

/**
 * Today's scoreboard (live, scheduled and finished games). Refreshes every 10 seconds
 * while a game is live, so the scores strip keeps up with the live chart, else every 60.
 */
export function useToday() {
  const [tick, setTick] = useState(0);
  const state = useAsync((s) => api.today(s), [tick]);
  const anyLive = state.data?.games.some((g) => g.status === "live") ?? false;
  useEffect(() => {
    const t = window.setInterval(() => setTick((n) => n + 1), anyLive ? 10_000 : 60_000);
    return () => window.clearInterval(t);
  }, [anyLive]);
  // Keep showing the last scoreboard while the next one loads.
  return { ...state, loading: state.loading && !state.data };
}
