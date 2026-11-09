import { useEffect, type ReactNode } from "react";
import { api, ApiError, type ModelCard } from "../api";
import { CalibrationChart, CalibrationTable, PhaseBars, seasonRange, SplitBar } from "../components/ModelCharts";
import { compactCount } from "../format";
import { useAsync } from "../hooks/useAsync";

const MODELS: Record<string, { label: string; inline: string; about: string }> = {
  logreg: {
    label: "Logistic regression",
    inline: "the logistic regression",
    about: "The baseline: a weighted sum of the inputs, turned into a probability.",
  },
  xgboost: {
    label: "XGBoost",
    inline: "XGBoost",
    about:
      "Gradient-boosted decision trees, constrained so that a bigger lead, the ball or a stronger team never lowers a team's chance.",
  },
  mlp: {
    label: "Neural network",
    inline: "the neural network",
    about: "A small network with two hidden layers of 32 units, trained in batches of 4,096 plays.",
  },
  endgame: {
    label: "End-game model",
    inline: "the end-game model",
    about:
      "XGBoost trained only on the last 3 minutes, where close finishes are a sliver of the data. It takes over from the best of the three as the clock runs from 3:00 to 2:00.",
  },
};
const label = (name: string) => MODELS[name]?.label ?? name;

const INPUTS = [
  ["Score margin", "Home score minus away score."],
  ["Time left", "Seconds left in regulation, or in the overtime period."],
  ["Overtime", "Whether the game is in overtime."],
  ["Possession", "Who has the ball, from the last make, rebound or turnover."],
  ["Team strength", "Gap in each team's point differential so far this season."],
  ["Margin × time", "The lead scaled by time left: 8 points means more late."],
];

const fmt = (n: number) => n.toLocaleString("en-US");
const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;
/** Rounds down near 100% so 99.95% never reads as a certainty. */
const pctBelow = (v: number) => `${(Math.floor(v * 1000) / 10).toFixed(1)}%`;
const pts = (v: number) => `${(v * 100).toFixed(1)} pts`;
const secs = (s: number | null) => (s === null ? null : s < 60 ? `${s.toFixed(1)} s` : `${Math.round(s / 60)} min`);

function trainedOn(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function Step({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <article className="card how-card">
      <h3 className="display">
        <span className="how-num">{n} /</span> {title}
      </h3>
      {children}
    </article>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="card stat">
      <span className="card-label">{label}</span>
      <span className="stat-value">{value}</span>
      <span className="stat-note">{note}</span>
    </div>
  );
}

function SourceNote({ card }: { card: ModelCard }) {
  if (card.data_source === "synthetic") {
    return <p className="how-flag">These numbers come from simulated development games, not real NBA results.</p>;
  }
  if (card.sample) {
    return (
      <p className="how-flag">
        Trained on a sample of each season's games. The full-season numbers arrive with the full data pull.
      </p>
    );
  }
  return null;
}

export function HowPage() {
  const state = useAsync((s) => api.model(s), []);
  const card = state.data;
  const prod = card?.production;
  const serving = prod ? card.models[prod] : undefined;
  const test = serving?.test ?? null;
  const split = card?.split ?? null;
  const tested = Object.entries(card?.models ?? {}).flatMap(([name, m]) => (m.test ? [{ name, scores: m.test }] : []));
  const allSeasons = split ? [...split.train.seasons, ...split.val.seasons, ...split.test.seasons] : [];
  const totalGames = split ? split.train.games + split.val.games + split.test.games : 0;
  const date = trainedOn(card?.trained_at ?? null);

  useEffect(() => {
    document.title = "How it's built · Clutch";
    return () => {
      document.title = "Clutch";
    };
  }, []);

  return (
    <div className="wrap how">
      <section className="hero">
        <h1 className="hero-title display">Behind the probability.</h1>
        <p className="lede">How Clutch learned to estimate each team's chance to win, and how well it does.</p>
      </section>

      <ol className="flow" aria-label="From game state to win probability">
        <li>Game state</li>
        <li aria-hidden className="flow-arrow">
          →
        </li>
        <li>{prod ? label(prod) : "Model"}</li>
        <li aria-hidden className="flow-arrow">
          →
        </li>
        <li className="on">Win probability</li>
      </ol>

      {split && test && (
        <div className="stats">
          <Stat
            label="Plays learned from"
            value={compactCount(split.train.plays)}
            note={`${fmt(split.train.games)} games, ${seasonRange(split.train.seasons)}`}
          />
          <Stat
            label="Games held out"
            value={fmt(split.test.games)}
            note={`The ${seasonRange(split.test.seasons)} season, never seen in training`}
          />
          <Stat
            label="Brier score"
            value={test.brier.toFixed(3)}
            note="Average squared error per play. 0 is perfect; saying 50% every time scores 0.25."
          />
          <Stat
            label="Calibration gap"
            value={pts(test.ece)}
            note="On average, how far the chance it gives is from how often that team actually won."
          />
        </div>
      )}
      {card && <SourceNote card={card} />}

      <h2 className="section-title display" id="training">
        How it's trained
      </h2>
      <p className="section-note">
        Split by season, never by play. Plays from the same game are nearly identical, so a random split would leak answers into
        the test.
      </p>
      {split && (
        <div className="card split-card">
          <SplitBar split={split} />
        </div>
      )}

      <div className="how-grid">
        <Step n="01" title="Every play becomes a row">
          <p>
            The data is NBA.com play-by-play for every regular-season game
            {allSeasons.length ? ` from ${seasonRange(allSeasons)}: ${fmt(totalGames)} games` : ""}. Each play becomes one row
            describing the game at that moment, labeled with whether the home team went on to win:
          </p>
          <dl className="inputs">
            {INPUTS.map(([term, def]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{def}</dd>
              </div>
            ))}
          </dl>
        </Step>

        <Step n="02" title="Four models learn from it">
          <p>
            Three whole-game models see the same rows and the same six inputs. A fourth learns only from the last 3 minutes.
          </p>
          <ul className="model-list">
            {Object.entries(card?.models ?? { logreg: null, xgboost: null, mlp: null }).map(([name, m]) => (
              <li key={name}>
                <div className="model-name">
                  <strong>{label(name)}</strong>
                  {name === prod && <span className="pill brand">Serving the site</span>}
                </div>
                <p>{MODELS[name]?.about}</p>
                {m && (
                  <p className="model-meta num">
                    {[
                      m.val && `Validation Brier ${m.val.brier.toFixed(4)}`,
                      name === "xgboost" && card?.xgboost_trees && `${card.xgboost_trees} trees`,
                      secs(m.train_seconds) && `trained in ${secs(m.train_seconds)}`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Step>

        <Step n="03" title="The validation season picks one">
          <p>
            Each model is scored on {split ? seasonRange(split.val.seasons) : "a held-back season"}, a season none of them trained
            on, and the lowest Brier score serves the site.
            {prod && serving?.val && (
              <>
                {" "}
                Right now that's <strong>{MODELS[prod]?.inline ?? prod}</strong>, at {serving.val.brier.toFixed(4)}.
              </>
            )}
          </p>
          <p>
            The same season decides when training stops. XGBoost keeps adding trees until 50 rounds go by without improvement
            {card?.xgboost_trees ? `, which took ${card.xgboost_trees} trees` : ""}. The network stops after 4 passes over the data
            without improvement.
          </p>
          {card?.calibrated && (
            <p>An isotonic calibration, fit on the same season, then adjusts the output so its percentages run true.</p>
          )}
        </Step>

        <Step n="04" title="Tested once, then put to work">
          <p>
            Only after the pick does the model see {split ? seasonRange(split.test.seasons) : "the test season"}. Its scores are
            below.
          </p>
          <p>
            On the site, replays are scored ahead of time. Tonight's games are scored as each play arrives, checking the NBA feed
            every 5 seconds.
          </p>
        </Step>
      </div>

      <h2 className="section-title display" id="results">
        How it scores
      </h2>
      {split && test && prod ? (
        <>
          <p className="section-note">
            {seasonRange(split.test.seasons)}: {fmt(split.test.games)} games and {fmt(split.test.plays)} plays the models never
            saw. Lower is better in every column.
          </p>
          <div className="card table-card">
            <table className="plays results">
              <thead>
                <tr>
                  <th>Model</th>
                  <th className="r">Brier score</th>
                  <th className="r hide-sm">Log loss</th>
                  <th className="r">Calibration gap</th>
                  <th className="r hide-sm">Final 2 minutes</th>
                </tr>
              </thead>
              <tbody className="num">
                {tested.map(({ name, scores }) => (
                  <tr key={name} className={name === prod ? "on" : undefined}>
                    <td>
                      <span className="model-name">
                        {label(name)}
                        {name === prod && <span className="pill brand">Serving</span>}
                      </span>
                    </td>
                    <td className="r">{scores.brier.toFixed(4)}</td>
                    <td className="r hide-sm">{scores.log_loss.toFixed(4)}</td>
                    <td className="r">{pts(scores.ece)}</td>
                    <td className="r hide-sm">{scores.phases.last_2_minutes?.brier.toFixed(4) ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="how-charts">
            <article className="card chart-panel">
              <span className="card-label">Calibration · {label(prod)}</span>
              <h3 className="panel-title">When it says 70%, does that team win 70% of the time?</h3>
              <CalibrationChart bins={test.bins} />
              <p className="panel-note">
                Each dot groups the test plays by the chance the model gave. On the dashed line, that chance came true exactly; the
                shaded band is within 5 points. Biggest miss: {pts(test.max_bin_gap)}.
              </p>
              <CalibrationTable bins={test.bins} />
            </article>

            <article className="card chart-panel">
              <span className="card-label">Error by game phase · {label(prod)}</span>
              <h3 className="panel-title">It gets sharper as the game goes on.</h3>
              <PhaseBars phases={test.phases} />
              <p className="panel-note">
                Brier score of the plays in each part of the game. Early on a lot can still change; by the final minutes the outcome
                is mostly settled.
              </p>
              {(test.final_play || test.tipoff) && (
                <dl className="checks">
                  {test.final_play && (
                    <div>
                      <dt>At the final play</dt>
                      <dd>
                        Gives the winner <strong className="num">{pctBelow(test.final_play.mean_prob_on_winner)}</strong> on average.
                      </dd>
                    </div>
                  )}
                  {test.tipoff && (
                    <div>
                      <dt>At tipoff</dt>
                      <dd>
                        Home teams won <strong className="num">{pct(test.tipoff.home_win_rate)}</strong> of test games; the model
                        gave them <strong className="num">{pct(test.tipoff.mean_prob)}</strong> on average, tracking the
                        team-strength gap (correlation {test.tipoff.corr_with_strength_gap.toFixed(2)}).
                      </dd>
                    </div>
                  )}
                </dl>
              )}
            </article>
          </div>
        </>
      ) : (
        !state.loading && (
          <p className="notice">
            {state.error && !(state.error instanceof ApiError && state.error.status === 404)
              ? "Can't load the model's results right now."
              : "Test-season results aren't available yet."}
          </p>
        )
      )}

      <p className="footnote how-foot">
        {date ? `Model trained ${date}. ` : ""}Model estimates, not guarantees.
      </p>
    </div>
  );
}
