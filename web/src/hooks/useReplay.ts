import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl, type Play } from "../api";

export type ReplayStatus = "idle" | "connecting" | "playing" | "paused" | "ended" | "error";

export const SPEEDS = [1, 10, 60] as const;

/** Streams a finished game from WS /games/{id}/replay and exposes the controls. */
export function useReplay(gameId: string) {
  const ws = useRef<WebSocket | null>(null);
  const [plays, setPlays] = useState<Play[]>([]);
  const [status, setStatus] = useState<ReplayStatus>("idle");
  const [speed, setSpeedState] = useState<number>(60);
  const [total, setTotal] = useState(0);

  const close = useCallback(() => {
    ws.current?.close();
    ws.current = null;
  }, []);

  useEffect(() => close, [close, gameId]);

  const send = (msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  };

  const start = useCallback(
    (atSpeed: number = speed, from = 0) => {
      close();
      setPlays([]);
      setStatus("connecting");
      setSpeedState(atSpeed);
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
    [close, gameId, speed],
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
    pause: () => send({ cmd: "pause" }),
    resume: () => send({ cmd: "play" }),
    restart: () => {
      if (ws.current) send({ cmd: "restart" });
      else start(speed);
    },
    setSpeed: (s: number) => {
      setSpeedState(s);
      send({ cmd: "speed", speed: s });
    },
    /** Jump to play i (the slider and quarter buttons). Starts the replay there if it isn't running. */
    seek: (i: number) => {
      if (ws.current?.readyState === WebSocket.OPEN) send({ cmd: "seek", i });
      else start(speed, i);
    },
  };
}
