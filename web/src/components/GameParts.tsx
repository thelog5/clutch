import { useEffect, useRef, useState, type ReactNode } from "react";
import type { GameSummary, Play, Team } from "../api";
import { change, gameDate, nickname, pct, periodLabel, playMoment, shortDate, statusLine, swingSize } from "../format";
import { SPEEDS, type ReplayStatus } from "../hooks/useReplay";
import { useMediaQuery } from "../hooks/useTheme";
import { logoUrl, teamColors } from "../teams";

/** The team's logo, always shown next to the abbreviation; a two-tone swatch if the logo can't load. */
export function TeamBadge({ abbr, size = 22 }: { abbr: string; size?: number }) {
  const dark = useMediaQuery("(prefers-color-scheme: dark)");
  const [failed, setFailed] = useState(false);
  const src = logoUrl(abbr, dark);
  if (src && !failed) {
    return (
      <img
        className="badge logo"
        src={src}
        width={size}
        height={size}
        alt=""
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
      />
    );
  }
  const [a, b] = teamColors(abbr);
  return (
    <span
      className="badge"
      style={{ width: size, height: size, background: `linear-gradient(135deg, ${a} 0 58%, ${b} 58% 100%)` }}
      aria-hidden
    />
  );
}

/** Badge, abbreviation and (optionally) score on one line. */
export function TeamLine({ team, score, dim = false }: { team: Team; score?: number | null; dim?: boolean }) {
  return (
    <div className={`team-line${dim ? " dim" : ""}`}>
      <TeamBadge abbr={team.abbr} />
      <span className="abbr">{team.abbr}</span>
      {score != null && <span className="score num">{score}</span>}
    </div>
  );
}

export function LivePill({ label = "Live" }: { label?: string }) {
  return <span className="pill live">{label}</span>;
}

/** Status for a game card: Live + clock, Final + date, or tipoff time. */
export function GameStatus({ game, current }: { game: GameSummary; current?: Play }) {
  if (game.status === "live")
    return (
      <div className="game-status">
        <LivePill />
        <span className="num">{current ? playMoment(current) : statusLine(game)}</span>
      </div>
    );
  if (game.status === "final")
    return (
      <div className="game-status">
        <span className="pill">Final</span>
        {game.date && <span className="num">{shortDate(game.date)}</span>}
      </div>
    );
  return (
    <div className="game-status">
      <span className="num">{statusLine(game)}</span>
    </div>
  );
}

/** "BOS 32%   NYK 68%" over a bar; the favored side is solid orange. */
export function ProbSplit({ home, away, prob }: { home: Team; away: Team; prob: number }) {
  const homeLeads = prob >= 0.5;
  return (
    <div className="split">
      <div className="split-labels">
        <span className={homeLeads ? "" : "lead"}>
          {away.abbr} <b className="num">{pct(1 - prob)}</b>
        </span>
        <span className={homeLeads ? "lead" : ""}>
          {home.abbr} <b className="num">{pct(prob)}</b>
        </span>
      </div>
      <div className="split-bar" aria-hidden>
        <span className={homeLeads ? "" : "on"} style={{ width: `${(1 - prob) * 100}%` }} />
        <span className={homeLeads ? "on" : ""} style={{ width: `${prob * 100}%` }} />
      </div>
    </div>
  );
}

export type BoardMode = "live" | "replay" | "final" | "scheduled";

/** Game center score bar: both teams, status and the win probability. */
export function Scoreboard({
  game,
  current,
  mode,
  prob,
  probLabel,
  extra,
}: {
  game: GameSummary;
  current?: Play;
  mode: BoardMode;
  prob: number | null;
  probLabel: string;
  extra?: ReactNode;
}) {
  const home = current ? current.home_score : game.home.score;
  const away = current ? current.away_score : game.away.score;
  const started = mode !== "scheduled";
  const decided = mode === "final" && home !== away;
  const side = (team: Team, score: number, won: boolean, tag?: string) => (
    <div className={`sb-team${decided && !won ? " dim" : ""}`}>
      <TeamBadge abbr={team.abbr} size={30} />
      <div className="sb-name">
        <span className="abbr">{team.abbr}</span>
        <span className="sb-nick">
          {nickname(team.name, team.abbr)}
          {tag && <span className="muted"> · {tag}</span>}
        </span>
      </div>
      {started && <span className="score num">{score}</span>}
    </div>
  );
  return (
    <section className="card scoreboard" aria-label="Score">
      {side(game.away, away, away > home)}
      {side(game.home, home, home > away, "home")}
      <div className="sb-status">
        {mode === "live" && <LivePill />}
        {mode === "replay" && <span className="pill brand">Replay</span>}
        {mode === "final" && <span className="pill">Final</span>}
        <span className="num">
          {current ? playMoment(current) : mode === "final" ? gameDate(game.date) : statusLine(game)}
        </span>
        {extra}
      </div>
      {prob !== null && (
        <div className="sb-prob" aria-live="polite">
          <span className="card-label">{probLabel}</span>
          <ProbSplit home={game.home} away={game.away} prob={prob} />
        </div>
      )}
    </section>
  );
}

/** Plays, latest first, with the home team's chance after each and the change it caused. */
export function PlayTable({
  plays,
  game,
  limit,
  highlight = false,
}: {
  plays: Play[];
  game: GameSummary;
  limit?: number;
  highlight?: boolean;
}) {
  const rows = [...plays].reverse().slice(0, limit ?? plays.length);
  return (
    <div className="table-scroll">
      <table className="plays">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Play</th>
            <th scope="col" className="r">
              {game.away.abbr}–{game.home.abbr}
            </th>
            <th scope="col" className="r">
              {game.home.abbr} win %
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p, k) => {
            const moved = Math.abs(p.delta) >= 0.005;
            return (
              <tr key={p.i} className={highlight && k === 0 ? "current" : undefined}>
                <td className="num nowrap time">{playMoment(p)}</td>
                <td>{p.description}</td>
                <td className="r num nowrap">
                  {p.away_score}–{p.home_score}
                </td>
                <td className="r num nowrap">
                  <b>{pct(p.prob)}</b>
                  <span className={`delta ${moved ? (p.delta > 0 ? "up" : "down") : ""}`}>{moved ? change(p.delta, 0) : "–"}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function SwingCard({ game, swing, live }: { game: GameSummary; swing: Play | null; live: boolean }) {
  if (!swing) return null;
  const helped = swing.delta > 0 ? game.home : game.away;
  return (
    <section className="card swing" aria-label="Biggest swing">
      <div className="swing-size">
        <span className="swing-num num">{swingSize(swing.delta)}</span>
        <span className="swing-unit">toward the {nickname(helped.name, helped.abbr)}</span>
      </div>
      <div className="swing-body">
        <h3 className="card-label">{live ? "Biggest swing so far" : "Biggest swing"}</h3>
        <p className="swing-play">{swing.description}</p>
        <p className="muted num">
          {playMoment(swing)}, {game.away.abbr} {swing.away_score}, {game.home.abbr} {swing.home_score}. The chance the{" "}
          {nickname(game.home.name, game.home.abbr)} win went from {pct(swing.prob - swing.delta)} to {pct(swing.prob)}.
        </p>
      </div>
    </section>
  );
}

interface ReplayBarProps {
  status: ReplayStatus;
  speed: number;
  /** Plays shown so far, and in the whole game. */
  position: number;
  total: number;
  /** First play index of each period, for the quarter buttons. */
  periods: { period: number; start: number }[];
  currentPeriod?: number;
  onToggle: () => void;
  onSpeed: (s: number) => void;
  onSeek: (i: number) => void;
}

export function ReplayBar(props: ReplayBarProps) {
  const { status, speed, position, total } = props;
  const running = status === "playing" || status === "connecting";
  const [pending, setPending] = useState<number | null>(null);
  const dragging = useRef(false);
  const timer = useRef<number>();

  // Follow the stream again once a seek has landed (not while the thumb is held).
  useEffect(() => {
    if (!dragging.current) setPending(null);
  }, [position]);

  const commit = (i: number, wait = 0) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => props.onSeek(i), wait);
  };

  const value = pending ?? position;
  const fill = total ? (value / total) * 100 : 0;

  return (
    <div className="card replay-bar" role="group" aria-label="Replay controls">
      <button className="primary play-btn" onClick={props.onToggle}>
        <span className={running ? "icon-pause" : "icon-play"} aria-hidden />
        {running ? "Pause" : status === "ended" ? "Replay" : "Play"}
      </button>
      <label className="speed">
        <span className="visually-hidden">Replay speed</span>
        <select value={speed} onChange={(e) => props.onSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}x
            </option>
          ))}
        </select>
      </label>
      <input
        type="range"
        className="scrub"
        min={0}
        max={total}
        value={value}
        style={{ ["--fill" as string]: `${fill}%` }}
        aria-label="Replay position"
        aria-valuetext={`Play ${value} of ${total}`}
        onPointerDown={() => (dragging.current = true)}
        onPointerUp={(e) => {
          dragging.current = false;
          commit(Number(e.currentTarget.value));
        }}
        onPointerCancel={() => (dragging.current = false)}
        onChange={(e) => {
          const v = Number(e.target.value);
          setPending(v);
          if (!dragging.current) commit(v, 200); // keyboard: settle on the last key press
        }}
      />
      <div className="quarters" role="group" aria-label="Jump to period">
        {props.periods.map((p) => (
          <button key={p.period} aria-pressed={props.currentPeriod === p.period} onClick={() => props.onSeek(p.start)}>
            {periodLabel(p.period)}
          </button>
        ))}
      </div>
    </div>
  );
}

export function CopyLink({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="ghost"
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
