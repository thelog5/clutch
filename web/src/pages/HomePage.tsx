import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type GameSummary, type Meta } from "../api";
import { ProbChart } from "../components/ProbChart";
import { gameDate, nickname, pct, shortDate, statusLine, swingSize } from "../format";
import { useAsync } from "../hooks/useAsync";
import { useTheme } from "../hooks/useTheme";
import { pickColors } from "../teams";

export function HomePage({ meta }: { meta?: Meta }) {
  return (
    <div className="wrap">
      <Hero meta={meta} />
      <Tonight />
      <PastGames meta={meta} />
    </div>
  );
}

function Hero({ meta }: { meta?: Meta }) {
  // Feature the most dramatic game of the latest finished season.
  const season = meta?.seasons.find((s) => s !== meta.seasons[0]) ?? meta?.seasons[0];
  const featured = useAsync(
    async (s) => {
      if (!season) return undefined;
      const page = await api.games({ season, sort: "swing", limit: 1 }, s);
      return page.games[0] ? api.series(page.games[0].id, s) : undefined;
    },
    [season],
  );
  const f = featured.data;

  return (
    <section className="hero">
      <h1 className="hero-title display">Up 8 with two minutes left isn't up 8 at halftime.</h1>
      <p className="lede">
        Clutch puts a number on how safe a lead is. After every play, it shows each team's chance to win, live for tonight's games and
        on replay for any game from the last two seasons.
      </p>
      {f && (
        <figure className="hero-figure">
          <figcaption>
            <Link to={`/game/${f.game.id}`} className="hero-game">
              {f.game.away.name} at {f.game.home.name}
            </Link>
            <span className="muted num">
              {gameDate(f.game.date)}, final {f.game.away.score}–{f.game.home.score}
            </span>
          </figcaption>
          <div className="chart-panel">
            <ProbChart plays={f.plays} home={f.game.home} away={f.game.away} swing={f.biggest_swing} compact />
          </div>
          <div className="hero-actions">
            <Link to={`/game/${f.game.id}?replay=60`} className="button primary">
              Replay this game at 60x
            </Link>
            {f.biggest_swing && (
              <span className="muted">
                Biggest swing: {swingSize(f.biggest_swing.delta)} on "{f.biggest_swing.description}"
              </span>
            )}
          </div>
        </figure>
      )}
      {featured.error && <ApiProblem error={featured.error} />}
    </section>
  );
}

function ApiProblem({ error }: { error: Error }) {
  return (
    <div className="notice" style={{ marginTop: 24 }}>
      <strong>Games aren't loading.</strong> {error.message} If you're running locally, start the API with <code>make api</code>.
    </div>
  );
}

function Tonight() {
  const today = useAsync((s) => api.today(s), []);
  const [tick, setTick] = useState(0);
  const refreshed = useAsync((s) => (tick ? api.today(s) : Promise.resolve(undefined)), [tick]);

  useEffect(() => {
    const t = window.setInterval(() => setTick((n) => n + 1), 30_000);
    return () => window.clearInterval(t);
  }, []);

  const data = refreshed.data ?? today.data;
  const games = data?.games ?? [];

  return (
    <section aria-labelledby="tonight">
      <h2 id="tonight" className="section-title">
        Tonight
      </h2>
      {today.loading && <p className="muted">Checking tonight's schedule…</p>}
      {data && data.live_ok === false && (
        <p className="section-note">The live scoreboard can't be reached right now, so tonight's games aren't shown. Replays below still work.</p>
      )}
      {data && data.live_ok !== false && games.length === 0 && <p className="section-note">No games today. Pick a past game below to replay it.</p>}
      {games.length > 0 && (
        <>
          <p className="section-note">Updates every 30 seconds. Open a game to follow it play by play.</p>
          <ul className="game-list">
            {games.map((g) => (
              <TonightRow key={g.id} g={g} />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function TonightRow({ g }: { g: GameSummary }) {
  const { dark, colors } = useTheme();
  const team = pickColors(g.home.abbr, g.away.abbr, colors.surface, dark);
  const started = g.status !== "scheduled";
  return (
    <li>
      <Link to={`/game/${g.id}`} className="game-row">
        <span className="row-status num">{g.status === "live" ? <span className="live-pill">{statusLine(g)}</span> : statusLine(g)}</span>
        <span className="row-teams">
          <span>
            {g.away.abbr} {started && <span className="num">{g.away.score}</span>}
          </span>
          <span className="muted">at</span>
          <span>
            {g.home.abbr} {started && <span className="num">{g.home.score}</span>}
          </span>
        </span>
        {g.prob != null && (
          <span className="tug" aria-label={`${nickname(g.home.name, g.home.abbr)} ${pct(g.prob)} chance to win`}>
            <span className="tug-bar">
              <span style={{ width: `${(1 - g.prob) * 100}%`, background: team.away }} />
              <span style={{ width: `${g.prob * 100}%`, background: team.home }} />
            </span>
            <span className="tug-label num">
              {g.prob >= 0.5 ? g.home.abbr : g.away.abbr} {pct(Math.max(g.prob, 1 - g.prob))}
            </span>
          </span>
        )}
      </Link>
    </li>
  );
}

const SORTS = [
  { value: "date", label: "Most recent" },
  { value: "swing", label: "Biggest swing" },
  { value: "close", label: "Closest" },
];

function PastGames({ meta }: { meta?: Meta }) {
  const [team, setTeam] = useState("");
  const [season, setSeason] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("date");
  const [limit, setLimit] = useState(25);

  useEffect(() => {
    const t = window.setTimeout(() => setQuery(q), 250);
    return () => window.clearTimeout(t);
  }, [q]);
  useEffect(() => setLimit(25), [team, season, query, sort]);

  const result = useAsync((s) => api.games({ team, season, q: query, sort, limit }, s), [team, season, query, sort, limit]);
  const page = result.data;

  return (
    <section aria-labelledby="past">
      <h2 id="past" className="section-title">
        Past games
      </h2>
      <p className="section-note">Every game is ready to replay. Search by team, city or date.</p>
      <div className="filters">
        <label className="field grow">
          Search
          <input type="search" value={q} placeholder="Raptors, Boston, 2026-03-07" onChange={(e) => setQ(e.target.value)} />
        </label>
        <label className="field">
          Team
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="">All teams</option>
            {meta?.teams.map((t) => (
              <option key={t.abbr} value={t.abbr}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Season
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
          Sort
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
      {page && (
        <p className="muted result-count num" aria-live="polite">
          {page.total.toLocaleString()} {page.total === 1 ? "game" : "games"}
        </p>
      )}
      {page && page.total === 0 && <p className="section-note">No games match. Try a team name or clear the filters.</p>}
      <ul className="game-list">
        {page?.games.map((g) => (
          <PastRow key={g.id} g={g} />
        ))}
      </ul>
      {page && page.total > page.games.length && (
        <button className="feed-more" onClick={() => setLimit(limit + 25)} disabled={result.loading}>
          {result.loading ? "Loading…" : "Show 25 more"}
        </button>
      )}
    </section>
  );
}

function PastRow({ g }: { g: GameSummary }) {
  const homeWon = g.home.score > g.away.score;
  return (
    <li>
      <Link to={`/game/${g.id}`} className="game-row">
        <span className="row-status num">{shortDate(g.date)}</span>
        <span className="row-teams">
          <span className={homeWon ? "" : "winner"}>
            {g.away.abbr} <span className="num">{g.away.score}</span>
          </span>
          <span className="muted">at</span>
          <span className={homeWon ? "winner" : ""}>
            {g.home.abbr} <span className="num">{g.home.score}</span>
          </span>
        </span>
        {g.biggest_swing && (
          <span className="row-swing muted num">{swingSize(g.biggest_swing.delta)} swing</span>
        )}
      </Link>
    </li>
  );
}
