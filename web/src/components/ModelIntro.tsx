import { Link } from "react-router-dom";
import { api } from "../api";
import { compactCount } from "../format";
import { useAsync } from "../hooks/useAsync";
import { seasonRange } from "./ModelCharts";

const SERVING: Record<string, string> = {
  logreg: "the logistic regression",
  xgboost: "XGBoost",
  mlp: "the neural network",
  endgame: "the end-game model",
};
const STACK = ["Python", "pandas", "scikit-learn", "XGBoost", "PyTorch", "FastAPI", "WebSockets", "React", "TypeScript"];

/** Home-page summary of what the site is: an ML model, how it learned, how it was tested. Numbers from GET /model. */
export function ModelIntro() {
  const { data: card } = useAsync((s) => api.model(s), []);
  const split = card?.split;
  const test = card ? card.models[card.production]?.test : null;
  const fmt = (n: number) => n.toLocaleString("en-US");

  return (
    <section className="card intro" aria-labelledby="intro-title">
      <div className="intro-head">
        <div>
          <span className="card-label">What you're looking at</span>
          <h2 id="intro-title" className="intro-title">
            A machine-learning model that predicts who wins, after every play.
          </h2>
        </div>
        <Link to="/how" className="replay-link intro-link">
          How it's trained and tested →
        </Link>
      </div>

      <ol className="intro-steps">
        <li>
          <span className="how-num display">01</span>
          <h3>Learns from past games</h3>
          <p>
            {split ? (
              <>
                Trained on <strong className="num">{compactCount(split.train.plays)}</strong> plays from{" "}
                <strong className="num">{fmt(split.train.games)}</strong> NBA games ({seasonRange(split.train.seasons)}).
              </>
            ) : (
              <>Trained on three seasons of NBA play-by-play.</>
            )}{" "}
            It learns how leads, time left, possession and team strength have played out before.
          </p>
        </li>
        <li>
          <span className="how-num display">02</span>
          <h3>Three models compete</h3>
          <p>
            A logistic regression, XGBoost and a neural network learn from the same plays. The most accurate on a separate
            validation season serves the site{card && SERVING[card.production] ? `: right now ${SERVING[card.production]}` : ""}.
          </p>
        </li>
        <li>
          <span className="how-num display">03</span>
          <h3>Predicts every play</h3>
          <p>
            Each play changes the score, the clock and who has the ball. The model turns that into each team's chance to win, live
            during tonight's games.
          </p>
        </li>
        <li>
          <span className="how-num display">04</span>
          <h3>Tested on games it never saw</h3>
          <p>
            {split && test ? (
              <>
                Scored on all <strong className="num">{fmt(split.test.games)}</strong> games of {seasonRange(split.test.seasons)},
                held out from training. Its percentages land within{" "}
                <strong className="num">{(test.ece * 100).toFixed(1)} points</strong> of what actually happened, on average.
              </>
            ) : (
              <>Scored on a full season held out from training, so its numbers reflect new games, not memorized ones.</>
            )}
          </p>
        </li>
      </ol>

      <div className="intro-foot">
        <span className="card-label">Built with</span>
        <ul className="stack" aria-label="Built with">
          {STACK.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
        {card?.data_source === "synthetic" && <span className="footnote">Numbers from simulated development data.</span>}
      </div>
    </section>
  );
}
