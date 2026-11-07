import { useState } from "react";
import type { GameSummary, Play } from "../api";
import { change, gameDate, nickname, pct, playMoment, statusLine, swingSize } from "../format";
import { SPEEDS, type ReplayStatus } from "../hooks/useReplay";

export function GameHeader({ game, current }: { game: GameSummary; current?: Play }) {
  const home = current ? current.home_score : game.home.score;
  const away = current ? current.away_score : game.away.score;
  const final = game.status === "final" && !current;
  const awayWon = final && away > home;
  const homeWon = final && home > away;
  return (
    <header className="game-header">
      <div className="matchup">
        <div className={`side ${awayWon ? "won" : ""}`}>
          <span className="team-name display">{game.away.name}</span>
          <span className="team-score display num">{away}</span>
        </div>
        <div className={`side ${homeWon ? "won" : ""}`}>
          <span className="team-name display">
            {game.home.name} <span className="home-tag">home</span>
          </span>
          <span className="team-score display num">{home}</span>
        </div>
      </div>
      <p className="game-meta">
        <span>{current ? playMoment(current) : statusLine(game)}</span>
        {game.date && <span>{gameDate(game.date)}</span>}
      </p>
    </header>
  );
}

export function BigProb({ game, current }: { game: GameSummary; current?: Play }) {
  const p = current?.prob ?? game.prob ?? null;
  if (p === null) return null;
  const home = nickname(game.home.name, game.home.abbr);
  const away = nickname(game.away.name, game.away.abbr);
  return (
    <div className="big-prob" aria-live="polite">
      <span className="big-num display num">{pct(p)}</span>
      <div className="big-label">
        <span className="big-team">chance the {home} win</span>
        <span className="muted num">
          {away} {pct(1 - p)}
        </span>
      </div>
    </div>
  );
}

interface ControlsProps {
  status: ReplayStatus;
  speed: number;
  progress: string;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
  onSpeed: (s: number) => void;
  onFull: () => void;
  shareUrl: string;
}

export function ReplayControls(props: ControlsProps) {
  const { status, speed } = props;
  const running = status === "playing" || status === "connecting";
  const idle = status === "idle" || status === "error";
  return (
    <div className="controls" role="group" aria-label="Replay controls">
      {idle ? (
        <button className="primary" onClick={props.onStart}>
          Replay game
        </button>
      ) : running ? (
        <button className="primary" onClick={props.onPause}>
          Pause
        </button>
      ) : status === "ended" ? (
        <button className="primary" onClick={props.onRestart}>
          Replay again
        </button>
      ) : (
        <button className="primary" onClick={props.onResume}>
          Play
        </button>
      )}
      <div className="segmented" role="group" aria-label="Replay speed">
        {SPEEDS.map((s) => (
          <button key={s} aria-pressed={speed === s} onClick={() => props.onSpeed(s)}>
            {s}x
          </button>
        ))}
      </div>
      {!idle && (
        <>
          <button onClick={props.onRestart}>Restart</button>
          <button onClick={props.onFull}>Show full game</button>
        </>
      )}
      <span className="progress muted num">{props.progress}</span>
      <CopyLink url={props.shareUrl} />
    </div>
  );
}

function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="copy-link"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(url);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1800);
        } catch {
          window.prompt("Copy this link", url);
        }
      }}
    >
      {copied ? "Link copied" : "Copy link"}
    </button>
  );
}

export function SwingCard({ game, swing, live }: { game: GameSummary; swing: Play | null; live: boolean }) {
  if (!swing) return null;
  const helped = swing.delta > 0 ? game.home : game.away;
  return (
    <section className="swing" aria-label="Biggest swing">
      <div className="swing-size">
        <span className="display num">{swingSize(swing.delta)}</span>
        <span className="swing-unit">swing toward the {nickname(helped.name, helped.abbr)}</span>
      </div>
      <div className="swing-body">
        <h3>{live ? "Biggest swing so far" : "Biggest swing"}</h3>
        <p className="swing-play">{swing.description}</p>
        <p className="muted num">
          {playMoment(swing)}, {game.away.abbr} {swing.away_score}, {game.home.abbr} {swing.home_score}. The chance the{" "}
          {nickname(game.home.name, game.home.abbr)} win went from {pct(swing.prob - swing.delta)} to {pct(swing.prob)}.
        </p>
      </div>
    </section>
  );
}

export function PlayFeed({ plays, game }: { plays: Play[]; game: GameSummary }) {
  const [all, setAll] = useState(false);
  if (!plays.length) return null;
  const recent = [...plays].reverse();
  const shown = all ? recent : recent.slice(0, 12);
  return (
    <section className="feed" aria-label="Play by play">
      <h2 className="section-title">Play by play</h2>
      <div className="table-scroll">
      <table className="feed-table">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Play</th>
            <th scope="col" className="r">
              {game.away.abbr}–{game.home.abbr}
            </th>
            <th scope="col" className="r">
              {game.home.abbr} chance
            </th>
            <th scope="col" className="r">
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {shown.map((p) => (
            <tr key={p.i}>
              <td className="num nowrap">{playMoment(p)}</td>
              <td>{p.description}</td>
              <td className="r num nowrap">
                {p.away_score}–{p.home_score}
              </td>
              <td className="r num">{pct(p.prob)}</td>
              <td className={`r num nowrap delta ${p.delta > 0.0005 ? "up" : p.delta < -0.0005 ? "down" : ""}`}>
                {Math.abs(p.delta) < 0.0005 ? "–" : change(p.delta)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {recent.length > 12 && (
        <button className="feed-more" onClick={() => setAll(!all)}>
          {all ? "Show latest 12" : `Show all ${recent.length} plays`}
        </button>
      )}
    </section>
  );
}
