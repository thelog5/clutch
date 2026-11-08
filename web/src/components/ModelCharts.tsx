import { useState, type CSSProperties } from "react";
import type { CalibrationBin, ModelCard, Phase, TestScores } from "../api";

const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");

export function seasonRange(seasons: string[]): string {
  return seasons.length > 1 ? `${seasons[0]} to ${seasons[seasons.length - 1]}` : (seasons[0] ?? "");
}

/* -- train / validate / test split, sized by plays -------------------------- */

const SPLIT_PARTS = [
  ["train", "Train", "The models learn from these"],
  ["val", "Validate", "Picks the model and stops training"],
  ["test", "Test", "Scored once, at the end"],
] as const;

export function SplitBar({ split }: { split: NonNullable<ModelCard["split"]> }) {
  const total = split.train.plays + split.val.plays + split.test.plays;
  return (
    <ol className="split-parts" aria-label="How the seasons are split">
      {SPLIT_PARTS.map(([key, label, role]) => {
        const part = split[key];
        const share = (part.plays / total) * 100;
        return (
          <li key={key} className={`split-part ${key}`} style={{ "--share": share } as CSSProperties}>
            <span className="split-seg" aria-hidden />
            <span className="split-cap">
              <strong>{label}</strong> <span className="split-seasons">{seasonRange(part.seasons)}</span>
              <span className="split-nums num">
                {fmt(part.games)} games · {fmt(part.plays)} plays
              </span>
              <span className="split-role">{role}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/* -- calibration: what the model said vs what happened ---------------------- */

const W = 324;
const H = 336;
const M = { top: 30, right: 14, bottom: 40, left: 42 };
const PW = W - M.left - M.right;
const PH = H - M.top - M.bottom;
const sx = (v: number) => M.left + v * PW;
const sy = (v: number) => M.top + (1 - v) * PH;
const TICKS = [0, 0.25, 0.5, 0.75, 1];
const BAND = 0.05;

function binLabel(b: CalibrationBin) {
  return `${Math.round(b.lo * 100)}–${Math.round(b.hi * 100)}%`;
}

export function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const [active, setActive] = useState<number | null>(null);
  const band = [
    [0, 0],
    [BAND, 0],
    [1, 1 - BAND],
    [1, 1],
    [1 - BAND, 1],
    [0, BAND],
  ]
    .map(([x, y]) => `${sx(x)},${sy(y)}`)
    .join(" ");
  const path = bins.map((b, i) => `${i ? "L" : "M"}${sx(b.mean_pred)},${sy(b.frac_pos)}`).join(" ");
  const tip = active === null ? null : bins[active];

  return (
    <div className="calib">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Calibration on the test season: predicted chance against how often the home team actually won, in 10 groups. The table below lists every group."
      >
        {TICKS.map((t) => (
          <g key={t} className="calib-grid">
            <line x1={sx(0)} x2={sx(1)} y1={sy(t)} y2={sy(t)} />
            <line x1={sx(t)} x2={sx(t)} y1={sy(0)} y2={sy(1)} />
            <text x={M.left - 8} y={sy(t)} dy="0.32em" textAnchor="end">
              {pct(t)}
            </text>
            <text x={sx(t)} y={sy(0) + 16} textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"}>
              {pct(t)}
            </text>
          </g>
        ))}
        <polygon className="calib-band" points={band} />
        <line className="calib-diag" x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} />
        <path className="calib-line" d={path} />
        {bins.map((b, i) => (
          <g
            key={b.lo}
            className={`calib-dot${active === i ? " on" : ""}`}
            tabIndex={0}
            role="img"
            aria-label={`Said ${binLabel(b)}: home team won ${pct(b.frac_pos, 1)} of ${fmt(b.n)} plays`}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
          >
            <circle className="hit" cx={sx(b.mean_pred)} cy={sy(b.frac_pos)} r={14} />
            <circle className="dot" cx={sx(b.mean_pred)} cy={sy(b.frac_pos)} r={active === i ? 6 : 4.5} />
          </g>
        ))}
        <text className="calib-axis" x={sx(0.5)} y={H - 4} textAnchor="middle">
          Chance the model gave the home team
        </text>
        <text className="calib-axis" x={0} y={12}>
          How often the home team won
        </text>
      </svg>
      {tip && (
        <div
          className={`chart-tip calib-tip ${tip.mean_pred < 0.3 ? "start" : tip.mean_pred > 0.7 ? "end" : ""} ${tip.frac_pos > 0.7 ? "below" : ""}`}
          style={{ left: `${(sx(tip.mean_pred) / W) * 100}%`, top: `${(sy(tip.frac_pos) / H) * 100}%` }}
          aria-hidden
        >
          <div className="tip-head">
            <span>Model said {binLabel(tip)}</span>
          </div>
          <div className="tip-prob num">
            {pct(tip.frac_pos, 1)}
            <span className="muted">won</span>
          </div>
          <div className="muted num">
            Average said {pct(tip.mean_pred, 1)} · {fmt(tip.n)} plays
          </div>
        </div>
      )}
    </div>
  );
}

export function CalibrationTable({ bins }: { bins: CalibrationBin[] }) {
  return (
    <details className="calib-table">
      <summary>Show as a table</summary>
      <table className="plays">
        <thead>
          <tr>
            <th>Model said</th>
            <th className="r">Average said</th>
            <th className="r">Home team won</th>
            <th className="r">Plays</th>
          </tr>
        </thead>
        <tbody className="num">
          {bins.map((b) => (
            <tr key={b.lo}>
              <td>{binLabel(b)}</td>
              <td className="r">{pct(b.mean_pred, 1)}</td>
              <td className="r">{pct(b.frac_pos, 1)}</td>
              <td className="r">{fmt(b.n)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/* -- Brier score by game phase ---------------------------------------------- */

const PHASES: [Phase, string][] = [
  ["first_half", "First half"],
  ["third_quarter", "Third quarter"],
  ["fourth_quarter", "Fourth quarter"],
  ["last_2_minutes", "Final 2 minutes"],
  ["overtime", "Overtime"],
];
/** Brier score of saying 50% on every play. */
export const COIN_FLIP = 0.25;

export function PhaseBars({ phases }: { phases: TestScores["phases"] }) {
  const rows = PHASES.filter(([key]) => phases[key]).map(([key, label]) => ({ key, label, ...phases[key]! }));
  const max = Math.max(COIN_FLIP, ...rows.map((r) => r.brier));
  return (
    <ul className="phase-bars">
      {rows.map((r) => (
        <li key={r.key} title={`${r.label}: Brier ${r.brier.toFixed(4)} over ${fmt(r.rows)} plays`}>
          <span className="phase-label">{r.label}</span>
          <span className="phase-track">
            <span className="phase-bar" style={{ width: `${(r.brier / max) * 100}%` }} />
          </span>
          <span className="phase-val num">{r.brier.toFixed(3)}</span>
        </li>
      ))}
      <li className="phase-ref" aria-hidden>
        <span />
        <span className="phase-track">
          <span>0</span>
          <span className="phase-coin" style={{ left: `${(COIN_FLIP / max) * 100}%` }}>
            {COIN_FLIP}: always saying 50%
          </span>
        </span>
        <span />
      </li>
    </ul>
  );
}
