import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, type GameSummary, type Play, type Series } from "../api";
import { ModelIntro } from "../components/ModelIntro";
import { GameStatus, LivePill, ProbSplit, TeamBadge, TeamLine } from "../components/GameParts";
import { ProbChart, Sparkline } from "../components/ProbChart";
import { nickname, shortDate, statusLine, swingSize, tipoffTime } from "../format";
import { useAsync } from "../hooks/useAsync";
import { useLive } from "../hooks/useLive";
import { useToday } from "../hooks/useToday";
import { CHART_NOTE, useMeta } from "../meta";

const ORDER = { live: 0, scheduled: 1, final: 2 } as const;

export function HomePage() {
  // Header links point at /#live, /#tonight and /#past; scroll there once the page renders.
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const t = window.setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" }), 50);
    return () => window.clearTimeout(t);
  }, [hash]);

  const today = useToday();
  const games = [...(today.data?.games ?? [])].sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  const live = games.filter((g) => g.status === "live");
  const rest = games.filter((g) => g.status !== "live");

  return (
    <div className="wrap">
      {games.length > 0 && <Ticker games={games} liveCount={live.length} />}
      <section className="hero">
        <h1 className="hero-title display">Every possession changes the game.</h1>
        <p className="lede">
          Clutch uses machine learning to estimate each NBA team's chance to win, updated after every play, live and on replay.
        </p>
      </section>
      <ModelIntro />
      {live.length > 0 ? <LiveNow games={live} /> : <FeaturedReplays />}
      <div className="home-split">
        <Tonight games={rest} loading={today.loading} liveOk={today.data?.live_ok} error={today.error} />
        <PastGames />
      </div>
    </div>
  );
}

function SectionTitle({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2 id={id} className="section-title display">
      {children}
    </h2>
  );
}

function ApiProblem({ error }: { error: Error }) {
  return (
    <div className="notice">
      <strong>Games aren't loading.</strong> {error.message} If you're running locally, start the API with <code>make api</code>.
    </div>
  );
}

/* -- scores strip ------------------------------------------------------ */

function Ticker({ games, liveCount }: { games: GameSummary[]; liveCount: number }) {
  return (
    <nav className="card ticker" aria-label="Today's scores">
      <span className={`ticker-label display${liveCount ? " is-live" : ""}`}>{liveCount ? `Live (${liveCount})` : "Today"}</span>
      <ul>
        {games.map((g) => {
          const started = g.status !== "scheduled";
          return (
            <li key={g.id}>
              <Link to={`/game/${g.id}`} className="tick">
                <span className="tick-teams num">
                  <span>
                    {g.away.abbr} {started && <b>{g.away.score}</b>}
                  </span>
                  <span>
                    {g.home.abbr} {started && <b>{g.home.score}</b>}
                  </span>
                </span>
                <span className="tick-status num">
                  {g.status === "live" ? statusLine(g) : g.status === "final" ? "Final" : tipoffTime(g.start_time_utc) || "Today"}
                  {g.status === "live" && <LivePill />}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/* -- live now ---------------------------------------------------------- */

function LiveNow({ games }: { games: GameSummary[] }) {
  const [first, ...others] = games;
  return (
    <section aria-labelledby="live">
      <SectionTitle id="live">Live now ({games.length})</SectionTitle>
      <div className={`feature-grid${others.length ? "" : " solo"}`}>
        <FeaturedLive game={first} />
        {others.length > 0 && (
          <div className="side-cards">
            {others.map((g) => (
              <LiveCard key={g.id} game={g} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function FeaturedLive({ game }: { game: GameSummary }) {
  const live = useLive(game.id, true);
  const info = live.game ?? game;
  const current: Play | undefined = live.plays[live.plays.length - 1];
  const prob = current?.prob ?? game.prob ?? null;
  return (
    <FeatureCard
      game={{ ...game, status: live.status === "final" ? "final" : "live" }}
      plays={live.plays}
      current={current}
      showCurrent={live.status === "live"}
      side={
        prob !== null && (
          <>
            <span className="card-label">Model win probability</span>
            <ProbSplit home={info.home} away={info.away} prob={prob} />
          </>
        )
      }
      action={
        <Link to={`/game/${game.id}`} className="button primary">
          Open game center <span aria-hidden>→</span>
        </Link>
      }
    />
  );
}

function LiveCard({ game }: { game: GameSummary }) {
  return (
    <Link to={`/game/${game.id}`} className="card side-card" aria-label={`${game.away.name} at ${game.home.name}, live`}>
      <div className="side-top">
        <div>
          <TeamLine team={game.away} score={game.away.score} />
          <TeamLine team={game.home} score={game.home.score} />
        </div>
        <GameStatus game={game} />
      </div>
      {game.prob != null && <ProbSplit home={game.home} away={game.away} prob={game.prob} />}
    </Link>
  );
}

/** The big card: teams, status, a side panel, the chart and an action. */
function FeatureCard({
  game,
  plays,
  current,
  showCurrent,
  side,
  action,
  swing,
}: {
  game: GameSummary;
  plays: Play[];
  current?: Play;
  showCurrent: boolean;
  side: ReactNode;
  action: ReactNode;
  swing?: Play | null;
}) {
  const home = current ? current.home_score : game.home.score;
  const away = current ? current.away_score : game.away.score;
  const final = game.status === "final";
  return (
    <article className="card feature">
      <div className="feature-top">
        <div className="feature-teams">
          <TeamLine team={game.away} score={away} dim={final && away < home} />
          <TeamLine team={game.home} score={home} dim={final && home < away} />
        </div>
        <GameStatus game={game} current={current} />
        <div className="feature-side">{side}</div>
      </div>
      <div className="feature-chart">
        <span className="card-label">Win probability ({game.home.abbr})</span>
        <ProbChart plays={plays} home={game.home} away={game.away} swing={swing} showCurrent={showCurrent} compact />
      </div>
      <div className="feature-foot">
        <span className="footnote">{CHART_NOTE}</span>
        {action}
      </div>
    </article>
  );
}

/* -- featured replays (nothing live) ------------------------------------ */

function FeaturedReplays() {
  const meta = useMeta();
  // The most dramatic games of the latest finished season.
  const season = meta?.seasons.find((s) => s !== meta.seasons[0]) ?? meta?.seasons[0];
  const picks = useAsync(
    async (s) => {
      if (!season) return [];
      const page = await api.games({ season, sort: "swing", limit: 3 }, s);
      return Promise.all(page.games.map((g) => api.series(g.id, s)));
    },
    [season],
  );
  const [first, ...others] = picks.data ?? [];

  return (
    <section aria-labelledby="live">
      <SectionTitle id="live">Biggest swings{season ? `, ${season}` : ""}</SectionTitle>
      <p className="section-note">No games are live right now. Replay the season's wildest finishes, play by play.</p>
      {picks.error && <ApiProblem error={picks.error} />}
      {first && (
        <div className={`feature-grid${others.length ? "" : " solo"}`}>
          <FeatureCard
            game={first.game}
            plays={first.plays}
            swing={first.biggest_swing}
            showCurrent={false}
            side={
              first.biggest_swing && (
                <>
                  <span className="card-label">Biggest swing</span>
                  <span className="feature-swing num">{swingSize(first.biggest_swing.delta)}</span>
                  <span className="muted feature-swing-desc">{first.biggest_swing.description}</span>
                </>
              )
            }
            action={
              <Link to={`/game/${first.game.id}?replay=60`} className="button primary">
                Replay at 60x <span aria-hidden>→</span>
              </Link>
            }
          />
          {others.length > 0 && (
            <div className="side-cards">
              {others.map((s) => (
                <ReplayCard key={s.game.id} series={s} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ReplayCard({ series }: { series: Series }) {
  const { game, plays, biggest_swing: swing } = series;
  const homeWon = game.home.score > game.away.score;
  return (
    <Link to={`/game/${game.id}`} className="card side-card" aria-label={`Replay ${game.away.name} at ${game.home.name}`}>
      <div className="side-top">
        <div>
          <TeamLine team={game.away} score={game.away.score} dim={homeWon} />
          <TeamLine team={game.home} score={game.home.score} dim={!homeWon} />
        </div>
        <GameStatus game={game} />
      </div>
      <Sparkline plays={plays} label={`${game.home.abbr} win probability over the game`} />
      {swing && (
        <p className="side-swing">
          <b className="num">{swingSize(swing.delta)}</b> swing <span className="muted">{swing.description}</span>
        </p>
      )}
    </Link>
  );
}

/* -- tonight -------------------------------------------------------------- */

function Tonight({
  games,
  loading,
  liveOk,
  error,
}: {
  games: GameSummary[];
  loading: boolean;
  liveOk?: boolean | null;
  error?: Error;
}) {
  return (
    <section aria-labelledby="tonight" className="tonight">
      <SectionTitle id="tonight">Tonight{games.length > 0 && ` (${games.length})`}</SectionTitle>
      {loading && <p className="muted">Checking tonight's schedule…</p>}
      {error && !loading && <p className="section-note">Tonight's scoreboard isn't loading right now.</p>}
      {liveOk === false && (
        <p className="section-note">The live scoreboard can't be reached right now, so tonight's games aren't shown. Replays still work.</p>
      )}
      {!loading && liveOk !== false && !error && games.length === 0 && (
        <p className="section-note">Nothing else on today's schedule. Pick a past game to replay it.</p>
      )}
      {games.length > 0 && (
        <ul className="tonight-list">
          {games.map((g) => (
            <li key={g.id}>
              <Link to={`/game/${g.id}`} className="card tonight-row">
                <span className="tonight-team">
                  <TeamBadge abbr={g.away.abbr} />
                  <span className="abbr">{g.away.abbr}</span>
                </span>
                <span className="muted at">at</span>
                <span className="tonight-team">
                  <TeamBadge abbr={g.home.abbr} />
                  <span className="abbr">{g.home.abbr}</span>
                </span>
                <span className="tonight-when num">
                  {g.status === "final" ? (
                    <>
                      Final <b>{g.away.score}–{g.home.score}</b>
                    </>
                  ) : (
                    tipoffTime(g.start_time_utc) || statusLine(g)
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/* -- past games ----------------------------------------------------------- */

const SORTS = [
  { value: "date", label: "Most recent" },
  { value: "swing", label: "Biggest swing" },
  { value: "close", label: "Closest" },
];

function PastGames() {
  const meta = useMeta();
  const [season, setSeason] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("date");
  const [limit, setLimit] = useState(10);

  useEffect(() => {
    const t = window.setTimeout(() => setQuery(q), 250);
    return () => window.clearTimeout(t);
  }, [q]);
  useEffect(() => setLimit(10), [season, query, sort]);

  const result = useAsync((s) => api.games({ season, q: query, sort, limit }, s), [season, query, sort, limit]);
  const page = result.data;

  return (
    <section aria-labelledby="past" className="past">
      <div className="section-head">
        <SectionTitle id="past">Past games</SectionTitle>
        {page && (
          <span className="muted num" aria-live="polite">
            {page.total.toLocaleString()} {page.total === 1 ? "game" : "games"}
          </span>
        )}
      </div>
      <div className="filters">
        <label className="field grow">
          <span className="visually-hidden">Search</span>
          <input type="search" value={q} placeholder="Search a team, city or date" onChange={(e) => setQ(e.target.value)} />
        </label>
        <label className="field">
          <span className="visually-hidden">Season</span>
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            <option value="">All seasons</option>
            {meta?.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="visually-hidden">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {result.error && <ApiProblem error={result.error} />}
      {page && page.total === 0 && <p className="section-note">No games match. Try a team name or clear the filters.</p>}
      {page && page.games.length > 0 && (
        <div className="card table-scroll">
          <table className="past-table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Final</th>
                <th scope="col" className="r hide-sm">
                  Biggest swing
                </th>
                <th scope="col">
                  <span className="visually-hidden">Replay</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {page.games.map((g) => (
                <PastRow key={g.id} g={g} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {page && page.total > page.games.length && (
        <button className="more" onClick={() => setLimit(limit + 25)} disabled={result.loading}>
          {result.loading ? "Loading…" : "Show 25 more"}
        </button>
      )}
    </section>
  );
}

function PastRow({ g }: { g: GameSummary }) {
  const homeWon = g.home.score > g.away.score;
  return (
    <tr>
      <td className="num nowrap muted">{shortDate(g.date)}</td>
      <td className="nowrap matchup num">
        <span className={homeWon ? "lost" : "won"}>
          {g.away.abbr} {g.away.score}
        </span>
        <span className="muted at"> at </span>
        <span className={homeWon ? "won" : "lost"}>
          {g.home.abbr} {g.home.score}
        </span>
      </td>
      <td className="r num muted hide-sm">{g.biggest_swing ? swingSize(g.biggest_swing.delta) : "–"}</td>
      <td className="r">
        <Link
          to={`/game/${g.id}`}
          className="replay-link"
          aria-label={`Replay ${nickname(g.away.name, g.away.abbr)} at ${nickname(g.home.name, g.home.abbr)}, ${shortDate(g.date)}`}
        >
          Replay <span aria-hidden>→</span>
        </Link>
      </td>
    </tr>
  );
}
