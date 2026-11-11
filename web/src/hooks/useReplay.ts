import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl, type Play } from "../api";

export type ReplayStatus = "idle" | "connecting" | "playing" | "paused" | "ended" | "error";

export const SPEEDS = [1, 10, 60] as const;

// The server's pacing (api/replay.py, api/settings.py), for replays run in the browser.
const MIN_GAP_GAME_SECONDS = 1.5;
const MAX_GAP_WALL_SECONDS = 30;

function gapMs(prev: Play, next: Play, speed: number): number {
  const game = Math.max(next.elapsed - prev.elapsed, MIN_GAP_GAME_SECONDS);
  return Math.min(game / speed, MAX_GAP_WALL_SECONDS) * 1000;
}

/** A replay run in the browser: its plays, how many are showing, and the timer to the next one. */
interface LocalReplay {
  plays: Play[];
  i: number;
  speed: number;
  paused: boolean;
  timer?: number;
}

/**
 * Replays a finished game and exposes the controls. Streams it from
 * WS /games/{id}/replay, or, given `saved` plays (a game saved with the site,
 * before the API has woken up), plays those in the browser at the same pace.
 */
export function useReplay(gameId: string, saved?: Play[]) {
  const ws = useRef<WebSocket | null>(null);
  const local = useRef<LocalReplay | null>(null);
  const savedPlays = useRef(saved);
  savedPlays.current = saved;
  const [plays, setPlays] = useState<Play[]>([]);
  const [status, setStatus] = useState<ReplayStatus>("idle");
  const [speed, setSpeedState] = useState<number>(60);
  const [total, setTotal] = useState(0);

  const close = useCallback(() => {
    ws.current?.close();
    ws.current = null;
    if (local.current) window.clearTimeout(local.current.timer);
    local.current = null;
  }, []);

  useEffect(() => close, [close, gameId]);

  const send = (msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  };

  // In the browser: show the next play, then wait as long as the game did before the one after.
  const advance = useCallback(() => {
    const r = local.current;
    if (!r || r.paused) return;
    window.clearTimeout(r.timer);
    if (r.i < r.plays.length) {
      r.i += 1;
      setPlays(r.plays.slice(0, r.i));
    }
    if (r.i >= r.plays.length) {
      setStatus("ended");
      return;
    }
    setStatus("playing");
    r.timer = window.setTimeout(advance, gapMs(r.plays[r.i - 1], r.plays[r.i], r.speed));
  }, []);

  const seekLocal = useCallback(
    (i: number) => {
      const r = local.current;
      if (!r) return;
      window.clearTimeout(r.timer);
      r.i = Math.min(Math.max(i, 0), r.plays.length);
      setPlays(r.plays.slice(0, r.i));
      advance();
    },
    [advance],
  );

  const start = useCallback(
    (atSpeed: number = speed, from = 0) => {
      close();
      setPlays([]);
      setSpeedState(atSpeed);
      const offline = savedPlays.current;
      if (offline?.length) {
        local.current = { plays: offline, i: 0, speed: atSpeed, paused: false };
        setTotal(offline.length);
        seekLocal(from);
        return;
      }
      setStatus("connecting");
      const query = `speed=${atSpeed}${from > 0 ? `&start=${from}` : ""}`;
      const sock = new WebSocket(wsUrl(`/games/${encodeURIComponent(gameId)}/replay?${query}`));
      ws.current = sock;
      sock.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
          case "init":
            setTotal(msg.total);
            setStatus("playing");
            break;
          case "play": {
            const { type: _type, ...play } = msg;
            setPlays((prev) => [...prev, play as Play]);
            break;
          }
          case "state":
            setStatus(msg.paused ? "paused" : "playing");
            setSpeedState(msg.speed);
            break;
          case "reset":
            setPlays([]);
            setStatus("playing");
            break;
          case "seek":
            setPlays(msg.plays);
            break;
          case "end":
            setStatus("ended");
            break;
          case "error":
            setStatus("error");
            break;
        }
      };
      sock.onerror = () => setStatus("error");
      sock.onclose = () => {
        if (ws.current === sock) ws.current = null;
      };
    },
    [close, gameId, seekLocal, speed],
  );

  return {
    plays,
    status,
    speed,
    total,
    active: status !== "idle" && status !== "error",
    start,
    stop: () => {
      close();
      setStatus("idle");
    },
    pause: () => {
      const r = local.current;
      if (!r) return send({ cmd: "pause" });
      r.paused = true;
      window.clearTimeout(r.timer);
      setStatus("paused");
    },
    resume: () => {
      const r = local.current;
      if (!r) return send({ cmd: "play" });
      r.paused = false;
      advance();
    },
    restart: () => {
      const r = local.current;
      if (r) {
        r.paused = false;
        seekLocal(0);
      } else if (ws.current) send({ cmd: "restart" });
      else start(speed);
    },
    setSpeed: (s: number) => {
      setSpeedState(s);
      const r = local.current;
      if (!r) return send({ cmd: "speed", speed: s });
      r.speed = s;
      advance(); // like the server: the next play comes right away, then the new pace
    },
    /** Jump to play i (the slider and quarter buttons). Starts the replay there if it isn't running. */
    seek: (i: number) => {
      if (local.current) seekLocal(i);
      else if (ws.current?.readyState === WebSocket.OPEN) send({ cmd: "seek", i });
      else start(speed, i);
    },
  };
}
