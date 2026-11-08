import { useId, useMemo } from "react";
import { Area, ComposedChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Play, Team } from "../api";
import { change, periodLabel, playMoment } from "../format";
import { useMediaQuery, useTheme } from "../hooks/useTheme";

const REG = 2880;
const QUARTER = 720;
const OT = 300;

interface Props {
  plays: Play[];
  home: Team;
  away: Team;
  swing?: Play | null;
  showCurrent?: boolean;
  compact?: boolean;
}

interface Point extends Play {
  x: number;
  y: number;
}

function periodBounds(maxElapsed: number) {
  const out: { period: number; start: number; end: number }[] = [];
  for (let p = 1; p <= 4; p++) out.push({ period: p, start: (p - 1) * QUARTER, end: p * QUARTER });
  let p = 5;
  while (REG + (p - 5) * OT < maxElapsed) {
    out.push({ period: p, start: REG + (p - 5) * OT, end: REG + (p - 4) * OT });
    p++;
  }
  return out;
}

/** The home team's chance to win after every play: one orange line over the game clock. */
export function ProbChart({ plays, home, away, swing, showCurrent = false, compact = false }: Props) {
  const { colors } = useTheme();
  const narrow = useMediaQuery("(max-width: 640px)");
  const gid = useId().replace(/:/g, "");

  const data: Point[] = useMemo(() => plays.map((p) => ({ ...p, x: p.elapsed, y: p.prob * 100 })), [plays]);
  const last = data[data.length - 1];
  const periods = periodBounds(Math.max(REG, last?.x ?? 0));
  const xMax = periods[periods.length - 1].end;
  const height = compact ? (narrow ? 190 : 220) : narrow ? 240 : 300;
  const swingPoint = swing ? data.find((d) => d.i === swing.i) : undefined;

  const first = data[0];
  const summary = last
    ? `Chance the ${home.abbr} win, play by play: ${Math.round(first.y)}% at the first play, ${Math.round(last.y)}% ` +
      `after the latest (${playMoment(last)}).` +
      (swingPoint ? ` Biggest swing ${Math.abs(swingPoint.delta * 100).toFixed(0)}% on ${swingPoint.description}.` : "")
    : `Chance the ${home.abbr} win. No plays yet.`;

  return (
    <div className="prob-chart" style={{ height }} role="img" aria-label={summary}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`fill-${gid}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={colors.brand} stopOpacity={0.28} />
              <stop offset="1" stopColor={colors.brand} stopOpacity={0.02} />
            </linearGradient>
          </defs>

          {periods.slice(1).map((p) => (
            <ReferenceLine key={p.period} x={p.start} stroke={colors.lineSoft} strokeWidth={1} />
          ))}
          {[25, 75, 100].map((y) => (
            <ReferenceLine key={y} y={y} stroke={colors.lineSoft} strokeWidth={1} />
          ))}
          <ReferenceLine y={50} stroke={colors.ink3} strokeDasharray="3 4" strokeWidth={1} />

          <XAxis
            type="number"
            dataKey="x"
            domain={[0, xMax]}
            ticks={periods.map((p) => (p.start + p.end) / 2)}
            tickFormatter={(v: number) => periodLabel(periods.find((p) => v > p.start && v < p.end)?.period ?? 1)}
            tick={{ fill: colors.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: colors.line }}
            height={26}
            allowDataOverflow
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: colors.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={narrow ? 38 : 44}
          />

          {swingPoint && <ReferenceLine x={swingPoint.x} stroke={colors.ink3} strokeDasharray="2 3" strokeWidth={1} />}

          <Area
            type="linear"
            dataKey="y"
            baseValue={0}
            stroke={colors.brand}
            strokeWidth={2.25}
            fill={`url(#fill-${gid})`}
            isAnimationActive={false}
            activeDot={{ r: 5, fill: colors.surface, stroke: colors.brand, strokeWidth: 2 }}
          />

          {swingPoint && (
            <ReferenceDot x={swingPoint.x} y={swingPoint.y} r={6} fill={colors.surface} stroke={colors.ink} strokeWidth={2} ifOverflow="visible" />
          )}
          {showCurrent && last && (
            <ReferenceDot x={last.x} y={last.y} r={6} fill={colors.brand} stroke={colors.surface} strokeWidth={2.5} ifOverflow="visible" />
          )}

          <Tooltip
            cursor={{ stroke: colors.ink3, strokeWidth: 1 }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as Point;
              const leader = p.prob >= 0.5 ? home : away;
              const share = p.prob >= 0.5 ? p.prob : 1 - p.prob;
              return (
                <div className="chart-tip">
                  <div className="tip-head num">
                    <span>{playMoment(p)}</span>
                    <span>
                      {away.abbr} {p.away_score}, {home.abbr} {p.home_score}
                    </span>
                  </div>
                  <div className="tip-prob">
                    {leader.abbr} {Math.round(share * 100)}%
                    {p.delta !== 0 && (
                      <span className={p.delta > 0 ? "delta up" : "delta down"}>
                        {home.abbr} {change(p.delta)}
                      </span>
                    )}
                  </div>
                  <div className="tip-desc">{p.description}</div>
                </div>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** A small trend line of the home team's chance, for game cards. */
export function Sparkline({ plays, label }: { plays: Play[]; label: string }) {
  if (plays.length < 2) return null;
  const xMax = Math.max(REG, plays[plays.length - 1].elapsed);
  const pts = plays.map((p) => `${((p.elapsed / xMax) * 100).toFixed(2)},${(40 - p.prob * 40).toFixed(2)}`).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={label}>
      <line x1="0" x2="100" y1="20" y2="20" className="spark-mid" vectorEffect="non-scaling-stroke" />
      <polyline points={pts} className="spark-line" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
