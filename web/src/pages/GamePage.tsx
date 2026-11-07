import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type GameSummary, type Play } from "../api";
import { ProbChart } from "../components/ProbChart";
import { BigProb, GameHeader, PlayFeed, ReplayControls, SwingCard } from "../components/GameParts";
import { gameDate, tipoffTime } from "../format";
import { useAsync } from "../hooks/useAsync";
import { useLive } from "../hooks/useLive";
import { SPEEDS, useReplay } from "../hooks/useReplay";

function biggest(plays: Play[]): Play | null {
  let best: Play | null = null;
  for (const p of plays.slice(1)) if (!best || Math.abs(p.delta) > Math.abs(best.delta)) best = p;
  return best && best.delta !== 0 ? best : null;
}

export function GamePage() {
  const { id = "" } = useParams();
  const summary = useAsync((s) => api.game(id, s), [id]);
  const game = summary.data;

  useEffect(() => {
    if (game) document.title = `${game.away.abbr} at ${game.home.abbr}${game.date ? `, ${gameDate(game.date)}` : ""} · Clutch`;
    return () => {
      document.title = "Clutch";
    };
  }, [game]);

  return (
    <div className="wrap">
      <Link to="/" className="back">
        All games
      </Link>
      {summary.loading && <p className="muted">Loading game…</p>}
      {summary.error && (
        <div className="notice">
          <strong>This game couldn't be loaded.</strong> {summary.error.message} Check the link, or pick a game from the{" "}
          <Link to="/">games list</Link>.
        </div>
      )}
      {game && (game.replay_available ? <FinishedGame game={game} /> : <TonightGame game={game} />)}
    </div>
  );
}

function FinishedGame({ game }: { game: GameSummary }) {
  const [search, setSearch] = useSearchParams();
  const series = useAsync((s) => api.series(game.id, s), [game.id]);
  const replay = useReplay(game.id);
  const autoplayed = useRef(false);

  // Shareable replay links: /game/:id?replay=60 starts the replay right away.
  useEffect(() => {
    const want = Number(search.get("replay"));
    if (!autoplayed.current && series.data && (SPEEDS as readonly number[]).includes(want)) {
      autoplayed.current = true;
      replay.start(want);
    }
  }, [series.data, search, replay]);

  const plays = replay.active ? replay.plays : (series.data?.plays ?? []);
  const current = replay.active ? plays[plays.length - 1] : undefined;
  const swing = useMemo(() => biggest(plays), [plays]);

  const shareUrl = useMemo(() => {
    const url = new URL(window.location.href);
    url.search = replay.active ? `?replay=${replay.speed}` : "";
    return url.toString();
  }, [replay.active, replay.speed]);

  return (
    <>
      <GameHeader game={game} current={current} />
      <BigProb game={game} current={current ?? plays[plays.length - 1]} />
      {series.error && <div className="notice">The probability series for this game couldn't be loaded. {series.error.message}</div>}
      <div className="chart-panel">
        {plays.length > 0 || replay.active ? (
          <ProbChart plays={plays} home={game.home} away={game.away} swing={swing} showCurrent={replay.active} />
        ) : (
          <div style={{ height: 340 }} />
        )}
      </div>
      <ReplayControls
        status={replay.status}
        speed={replay.speed}
        progress={replay.active ? `${plays.length} of ${replay.total} plays` : `${plays.length} plays`}
        onStart={() => replay.start(replay.speed)}
        onPause={replay.pause}
        onResume={replay.resume}
        onRestart={replay.restart}
        onSpeed={(s) => (replay.active ? replay.setSpeed(s) : replay.start(s))}
        onFull={() => {
          replay.stop();
          setSearch({}, { replace: true });
        }}
        shareUrl={shareUrl}
      />
      {replay.status === "error" && (
        <p className="muted">The replay stream disconnected. Press Replay game to start it again.</p>
      )}
      <SwingCard game={game} swing={swing} live={replay.active && replay.status !== "ended"} />
      <PlayFeed plays={plays} game={game} />
    </>
  );
}

/** "Updated 4s ago": how fresh the live feed is (the PRD target is within 15s of a play). */
function Freshness({ since }: { since: number | null }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  if (since === null) return null;
  const secs = Math.max(0, Math.round((now - since) / 1000));
  return <span className="muted num">{secs < 2 ? "Updated just now" : `Updated ${secs}s ago`}</span>;
}

function TonightGame({ game }: { game: GameSummary }) {
  const live = useLive(game.id, game.status !== "scheduled");
  const info = live.game ?? game;
  const plays = live.plays;
  const current = plays[plays.length - 1];
  const swing = useMemo(() => biggest(plays), [plays]);

  if (game.status === "scheduled") {
    return (
      <>
        <GameHeader game={game} />
        <BigProb game={game} />
        <div className="notice">
          <strong>Tips off {tipoffTime(game.start_time_utc) || "later today"}.</strong> The chart starts moving with the first play.
          The number above is the chance before tipoff, based on each team's point differential this season.
        </div>
      </>
    );
  }

  return (
    <>
      <GameHeader game={{ ...info, status: live.status === "final" ? "final" : "live" }} current={current} />
      <p className="game-meta">
        {live.status === "live" && <span className="live-pill">Live</span>}
        {live.status === "live" && <Freshness since={live.lastUpdate} />}
        {live.status === "reconnecting" && <span className="muted">Reconnecting to the live feed…</span>}
        {live.status === "final" && <span>Final</span>}
        {live.status === "unavailable" && <span className="muted">The live feed for this game isn't available.</span>}
      </p>
      <BigProb game={info} current={current} />
      <div className="chart-panel">
        <ProbChart plays={plays} home={info.home} away={info.away} swing={swing} showCurrent={live.status === "live"} />
      </div>
      <SwingCard game={info} swing={swing} live={live.status !== "final"} />
      <PlayFeed plays={plays} game={info} />
    </>
  );
}
