import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type GameSummary, type Play } from "../api";
import { ProbChart } from "../components/ProbChart";
import { CopyLink, PlayTable, ReplayBar, Scoreboard, SwingCard, type BoardMode } from "../components/GameParts";
import { gameDate, playMoment, tipoffTime } from "../format";
import { useAsync } from "../hooks/useAsync";
import { useLive } from "../hooks/useLive";
import { SPEEDS, useReplay } from "../hooks/useReplay";
import { CHART_NOTE } from "../meta";

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
    <div className="wrap game-page">
      <Link to="/" className="back">
        <span aria-hidden>←</span> Back to games
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

function PageTitle({ children }: { children?: ReactNode }) {
  return (
    <div className="page-title-row">
      <h1 className="page-title display">Game center</h1>
      {children}
    </div>
  );
}

type Tab = "overview" | "plays";

function Tabs({ tab, onTab, count }: { tab: Tab; onTab: (t: Tab) => void; count: number }) {
  return (
    <div className="tabs" role="tablist" aria-label="Game views">
      <button role="tab" aria-selected={tab === "overview"} onClick={() => onTab("overview")}>
        Overview
      </button>
      <button role="tab" aria-selected={tab === "plays"} onClick={() => onTab("plays")}>
        Play-by-play {count > 0 && <span className="muted num">{count}</span>}
      </button>
    </div>
  );
}

/** Chart card + latest plays card, side by side on wide screens. */
function Overview({
  game,
  plays,
  swing,
  showCurrent,
  chartActions,
  onAllPlays,
  footer,
}: {
  game: GameSummary;
  plays: Play[];
  swing: Play | null;
  showCurrent: boolean;
  chartActions?: ReactNode;
  onAllPlays: () => void;
  footer?: ReactNode;
}) {
  return (
    <>
      <div className="gc-grid">
        <section className="card chart-card" aria-label="Win probability chart">
          <div className="card-head">
            <h2 className="card-label">Win probability ({game.home.abbr})</h2>
            {chartActions}
          </div>
          {plays.length > 0 || showCurrent ? (
            <ProbChart plays={plays} home={game.home} away={game.away} swing={swing} showCurrent={showCurrent} />
          ) : (
            <div className="chart-empty muted">The chart starts with the first play.</div>
          )}
          <p className="footnote">{CHART_NOTE}</p>
        </section>
        <section className="card recent-card" aria-label="Latest plays">
          <div className="card-head">
            <h2 className="card-label">Latest plays</h2>
            {plays.length > 8 && (
              <button className="link-btn" onClick={onAllPlays}>
                All plays <span aria-hidden>→</span>
              </button>
            )}
          </div>
          {plays.length ? (
            <PlayTable plays={plays} game={game} limit={8} highlight={showCurrent} />
          ) : (
            <p className="muted">No plays yet.</p>
          )}
        </section>
      </div>
      {footer}
    </>
  );
}

function FinishedGame({ game }: { game: GameSummary }) {
  const [search, setSearch] = useSearchParams();
  const [tab, setTab] = useState<Tab>("overview");
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

  const all = useMemo(() => series.data?.plays ?? [], [series.data]);
  const plays = replay.active ? replay.plays : all;
  const current = replay.active ? plays[plays.length - 1] : undefined;
  const swing = useMemo(() => biggest(plays), [plays]);
  const periods = useMemo(() => {
    const out: { period: number; start: number }[] = [];
    all.forEach((p, i) => {
      if (!out.length || out[out.length - 1].period !== p.period) out.push({ period: p.period, start: i });
    });
    return out;
  }, [all]);

  const shareUrl = useMemo(() => {
    const url = new URL(window.location.href);
    url.search = replay.active ? `?replay=${replay.speed}` : "";
    return url.toString();
  }, [replay.active, replay.speed]);

  const mode: BoardMode = replay.active ? "replay" : "final";
  const prob = current ? current.prob : (all[0]?.prob ?? null);

  const toggle = () => {
    if (replay.status === "playing" || replay.status === "connecting") replay.pause();
    else if (replay.status === "paused") replay.resume();
    else if (replay.status === "ended") replay.restart();
    else replay.start(replay.speed);
  };

  return (
    <>
      <PageTitle>
        <CopyLink url={shareUrl} />
      </PageTitle>
      <Scoreboard game={game} current={current} mode={mode} prob={prob} probLabel={current ? "Win probability" : "At tipoff"} />
      {series.error && <div className="notice">The probability series for this game couldn't be loaded. {series.error.message}</div>}
      <Tabs tab={tab} onTab={setTab} count={plays.length} />
      {tab === "overview" ? (
        <Overview
          game={game}
          plays={plays}
          swing={swing}
          showCurrent={replay.active}
          onAllPlays={() => setTab("plays")}
          chartActions={
            replay.active && (
              <span className="chart-actions">
                <span className="muted num">{current ? playMoment(current) : "Starting…"}</span>
                <button
                  className="link-btn"
                  onClick={() => {
                    replay.stop();
                    setSearch({}, { replace: true });
                  }}
                >
                  Show full game
                </button>
              </span>
            )
          }
          footer={
            all.length > 0 && (
              <ReplayBar
                status={replay.status}
                speed={replay.speed}
                position={plays.length}
                total={all.length}
                periods={periods}
                currentPeriod={current?.period}
                onToggle={toggle}
                onSpeed={(s) => (replay.active ? replay.setSpeed(s) : replay.start(s))}
                onSeek={replay.seek}
              />
            )
          }
        />
      ) : (
        <section className="card" aria-label="Play by play">
          <PlayTable plays={plays} game={game} highlight={replay.active} />
        </section>
      )}
      {replay.status === "error" && <p className="muted">The replay stream disconnected. Press Play to start it again.</p>}
      <SwingCard game={game} swing={swing} live={replay.active && replay.status !== "ended"} />
    </>
  );
}

/** "Updated 4s ago": how fresh the live feed is (the target is within 15s of a play). */
function Freshness({ since }: { since: number | null }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  if (since === null) return null;
  const secs = Math.max(0, Math.round((now - since) / 1000));
  return <span className="muted num freshness">{secs < 2 ? "Updated just now" : `Updated ${secs}s ago`}</span>;
}

function TonightGame({ game }: { game: GameSummary }) {
  const [tab, setTab] = useState<Tab>("overview");
  const live = useLive(game.id, game.status !== "scheduled");
  const info = live.game ?? game;
  const plays = live.plays;
  const current = plays[plays.length - 1];
  const swing = useMemo(() => biggest(plays), [plays]);

  if (game.status === "scheduled") {
    return (
      <>
        <PageTitle />
        <Scoreboard game={game} mode="scheduled" prob={game.prob ?? null} probLabel="Before tipoff" />
        <div className="notice">
          <strong>Tips off {tipoffTime(game.start_time_utc) || "later today"}.</strong> The chart starts moving with the first play.
          The number above is the chance before tipoff, based on each team's point differential this season.
        </div>
      </>
    );
  }

  const status = (
    <>
      {live.status === "live" && <Freshness since={live.lastUpdate} />}
      {live.status === "reconnecting" && <span className="muted">Reconnecting…</span>}
      {live.status === "unavailable" && <span className="muted">Live feed unavailable</span>}
    </>
  );

  return (
    <>
      <PageTitle />
      <Scoreboard
        game={info}
        current={current}
        mode={live.status === "final" ? "final" : "live"}
        prob={current?.prob ?? info.prob ?? null}
        probLabel="Win probability"
        extra={status}
      />
      <Tabs tab={tab} onTab={setTab} count={plays.length} />
      {tab === "overview" ? (
        <Overview
          game={info}
          plays={plays}
          swing={swing}
          showCurrent={live.status === "live"}
          onAllPlays={() => setTab("plays")}
        />
      ) : (
        <section className="card" aria-label="Play by play">
          <PlayTable plays={plays} game={info} highlight={live.status === "live"} />
        </section>
      )}
      <SwingCard game={info} swing={swing} live={live.status !== "final"} />
    </>
  );
}
