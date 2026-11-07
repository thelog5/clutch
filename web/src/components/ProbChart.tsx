import { useId, useMemo } from "react";
import {
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Play, Team } from "../api";
import { change, periodLabel, playMoment } from "../format";
import { useMediaQuery, useTheme } from "../hooks/useTheme";
import { pickColors } from "../teams";

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

export function ProbChart({ plays, home, away, swing, showCurrent = false, compact = false }: Props) {
  const { dark, colors } = useTheme();
  const narrow = useMediaQuery("(max-width: 640px)");
  const gid = useId().replace(/:/g, "");
  const team = useMemo(() => pickColors(home.abbr, away.abbr, colors.surface, dark), [home.abbr, away.abbr, colors.surface, dark]);

  const data: Point[] = useMemo(() => plays.map((p) => ({ ...p, x: p.elapsed, y: p.prob * 100 })), [plays]);
  const last = data[data.length - 1];
  const maxX = Math.max(REG, last?.x ?? 0);
  const periods = periodBounds(maxX);
  const xMax = periods[periods.length - 1].end;

  const height = compact ? (narrow ? 200 : 240) : narrow ? 260 : 340;
  const margin = { top: 12, right: 12, bottom: 0, left: 0 };
  const xAxisHeight = 28;
  // Pixel rows of the 100% and 0% lines: the team-color split sits exactly at 50%.
  const yTop = margin.top;
  const yBottom = height - margin.bottom - xAxisHeight;

  const swingPoint = swing ? data.find((d) => d.i === swing.i) : undefined;

  return (
    <div className="prob-chart" style={{ height }}>
      <div className="edge-label edge-top" style={{ top: margin.top + 4 }}>
        <span className="chip" style={{ background: team.home }} aria-hidden />
        {home.abbr} wins
      </div>
      <div className="edge-label edge-bottom" style={{ bottom: margin.bottom + xAxisHeight + 6 }}>
        <span className="chip" style={{ background: team.away }} aria-hidden />
        {away.abbr} wins
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={margin}>
          <defs>
            <linearGradient id={`fill-${gid}`} gradientUnits="userSpaceOnUse" x1="0" x2="0" y1={yTop} y2={yBottom}>
              <stop offset="0" stopColor={team.home} stopOpacity={0.34} />
              <stop offset="0.5" stopColor={team.home} stopOpacity={0.05} />
              <stop offset="0.5" stopColor={team.away} stopOpacity={0.05} />
              <stop offset="1" stopColor={team.away} stopOpacity={0.34} />
            </linearGradient>
            <linearGradient id={`line-${gid}`} gradientUnits="userSpaceOnUse" x1="0" x2="0" y1={yTop} y2={yBottom}>
              <stop offset="0.5" stopColor={team.home} />
              <stop offset="0.5" stopColor={team.away} />
            </linearGradient>
          </defs>

          {periods
            .filter((p) => p.period % 2 === 0)
            .map((p) => (
              <ReferenceArea key={p.period} x1={p.start} x2={p.end} y1={0} y2={100} fill={colors.shade} fillOpacity={1} strokeOpacity={0} ifOverflow="hidden" />
            ))}

          <XAxis
            type="number"
            dataKey="x"
            domain={[0, xMax]}
            ticks={periods.map((p) => (p.start + p.end) / 2)}
            tickFormatter={(v: number) => periodLabel(periods.find((p) => v > p.start && v < p.end)?.period ?? 1)}
            tick={{ fill: colors.ink3, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: colors.line }}
            height={xAxisHeight}
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
            orientation="right"
          />
          <ReferenceLine y={50} stroke={colors.ink3} strokeDasharray="4 4" strokeWidth={1} />
          {[25, 75].map((y) => (
            <ReferenceLine key={y} y={y} stroke={colors.lineSoft} strokeWidth={1} />
          ))}

          {swingPoint && (
            <ReferenceLine x={swingPoint.x} stroke={colors.ink3} strokeDasharray="2 3" strokeWidth={1} />
          )}

          <Area
            type="linear"
            dataKey="y"
            baseValue={50}
            stroke="none"
            fill={`url(#fill-${gid})`}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line
            type="linear"
            dataKey="y"
            stroke={`url(#line-${gid})`}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5, fill: colors.surface, stroke: colors.ink, strokeWidth: 2 }}
            isAnimationActive={false}
          />

          {swingPoint && (
            <ReferenceDot x={swingPoint.x} y={swingPoint.y} r={6} fill={colors.surface} stroke={colors.ink} strokeWidth={2} ifOverflow="visible" />
          )}
          {showCurrent && last && (
            <ReferenceDot x={last.x} y={last.y} r={6} fill={colors.ball} stroke={colors.surface} strokeWidth={2} ifOverflow="visible" />
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
                      {home.abbr} {p.home_score}, {away.abbr} {p.away_score}
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
