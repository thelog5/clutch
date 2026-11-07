import { useEffect, useState } from "react";
import { wsUrl, type GameSummary, type Play } from "../api";

export type LiveStatus = "connecting" | "live" | "final" | "unavailable" | "reconnecting";

/** Follows WS /games/{id}/live; reconnects with backoff until the game ends. */
export function useLive(gameId: string, enabled: boolean) {
  const [plays, setPlays] = useState<Play[]>([]);
  const [game, setGame] = useState<GameSummary | undefined>();
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let sock: WebSocket | null = null;
    let stopped = false;
    let final = false;
    let attempt = 0;
    let timer: number | undefined;

    const connect = () => {
      sock = new WebSocket(wsUrl(`/games/${encodeURIComponent(gameId)}/live`));
      sock.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        setLastUpdate(Date.now());
        if (msg.type === "init") {
          attempt = 0;
          setGame(msg.game);
          setPlays(msg.plays);
          final = msg.final;
          setStatus(msg.final ? "final" : "live");
        } else if (msg.type === "play") {
          const { type: _type, ...play } = msg;
          setPlays((prev) => [...prev, play as Play]);
        } else if (msg.type === "reset") {
          setPlays(msg.plays);
        } else if (msg.type === "status" && msg.status === "final") {
          final = true;
          setStatus("final");
        } else if (msg.type === "error") {
          final = true; // nothing to reconnect to
          setStatus("unavailable");
        }
      };
      sock.onclose = () => {
        if (stopped || final) return;
        setStatus("reconnecting");
        attempt += 1;
        timer = window.setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempt));
      };
    };
    connect();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      sock?.close();
    };
  }, [gameId, enabled]);

  return { plays, game, status, lastUpdate };
}
