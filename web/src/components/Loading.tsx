import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { shortDate, swingSize } from "../format";
import { SNAPSHOT } from "../snapshot";

/** How long a wait gets before the wake-up note and the games to look at meanwhile. */
const SLOW_MS = 3000;

/**
 * A spinner with its label underneath. After a few seconds it explains the
 * wait (the free API sleeps when idle and takes up to a minute to start) and
 * offers this season's biggest swings, which are saved in the site and open
 * right away.
 */
export function Loading({ label, meanwhile = false }: { label: string; meanwhile?: boolean }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!meanwhile) return;
    const t = window.setTimeout(() => setSlow(true), SLOW_MS);
    return () => window.clearTimeout(t);
  }, [meanwhile]);

  return (
    <div className="loading">
      <div className="loading-status" role="status">
        <span className="spinner" aria-hidden />
        <span className="loading-label">{label}</span>
        {slow && <span className="loading-hint">The server naps when nobody's using it and can take up to a minute to wake up.</span>}
      </div>
      {slow && <Meanwhile />}
    </div>
  );
}

/** "Updating…" with a small wheel, next to a heading over data that's already showing. */
export function Updating({ label = "Updating…" }: { label?: string }) {
  return (
    <span className="updating" role="status">
      <span className="spinner" aria-hidden />
      {label}
    </span>
  );
}

function Meanwhile() {
  const { season, games } = SNAPSHOT.season_swings;
  return (
    <div className="meanwhile">
      <p className="meanwhile-title">In the meantime, this season's biggest swings ({season}):</p>
      <ul>
        {games.map(({ game, biggest_swing: swing }) => {
          const homeWon = game.home.score > game.away.score;
          return (
            <li key={game.id}>
              <Link to={`/game/${game.id}`} className="meanwhile-game">
                <span className="matchup num">
                  <span className={homeWon ? "lost" : "won"}>
                    {game.away.abbr} {game.away.score}
                  </span>
                  <span className="muted"> at </span>
                  <span className={homeWon ? "won" : "lost"}>
                    {game.home.abbr} {game.home.score}
                  </span>
                </span>
                <span className="muted num">{shortDate(game.date)}</span>
                {swing && <span className="meanwhile-swing num">{swingSize(swing.delta)} swing</span>}
                <span aria-hidden>→</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
