"use client";

import { useMemo, useState } from "react";

export type EquityPoint = {
  date: string;
  strategy: number;
  benchmark: number;
};

type Props = {
  points: EquityPoint[];
  /** Legend label for the benchmark series (defaults to "Buy & hold"). */
  benchmarkLabel?: string;
  height?: number;
};

const W = 840;
const PAD = { top: 16, right: 92, bottom: 28, left: 52 };

const money = (v: number) =>
  v >= 1000
    ? `$${(v / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })}k`
    : `$${v.toFixed(0)}`;

const year = (iso: string) => iso.slice(0, 4);

/**
 * Strategy equity vs. a buy & hold benchmark over the backtest window.
 * Single visual world (the dashboard is dark-only) — colours are painted
 * explicitly rather than via a theme flip. Series identity is carried by the
 * legend, the direct end-labels and the line style, never colour alone.
 */
export function EquityChart({
  points,
  benchmarkLabel = "Buy & hold",
  height = 300,
}: Props) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const geom = useMemo(() => {
    if (points.length < 2) return null;
    const H = height;
    const values = points.flatMap((p) => [p.strategy, p.benchmark]);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const span = hi - lo || 1;
    // equity never goes negative — don't let the padded floor imply it can
    const yLo = Math.max(0, lo - span * 0.06);
    const yHi = hi + span * 0.06;

    const x = (i: number) =>
      PAD.left + (i / (points.length - 1)) * (W - PAD.left - PAD.right);
    const y = (v: number) =>
      PAD.top + (1 - (v - yLo) / (yHi - yLo)) * (H - PAD.top - PAD.bottom);

    const line = (key: "strategy" | "benchmark") =>
      points
        .map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p[key])}`)
        .join(" ");

    const area = `${line("strategy")} L${x(points.length - 1)},${
      H - PAD.bottom
    } L${x(0)},${H - PAD.bottom} Z`;

    const gridVals = [0, 0.25, 0.5, 0.75, 1].map((t) => yLo + t * (yHi - yLo));

    // year boundaries for x ticks
    const ticks: { i: number; label: string }[] = [];
    let seen = "";
    points.forEach((p, i) => {
      const yr = year(p.date);
      if (yr !== seen) {
        ticks.push({ i, label: yr });
        seen = yr;
      }
    });

    return { H, x, y, line, area, gridVals, ticks, yLo, yHi };
  }, [points, height]);

  if (!geom) return null;
  const { H, x, y, line, area, gridVals, ticks } = geom;

  const last = points[points.length - 1];
  const hover = hoverIdx == null ? null : points[hoverIdx];

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const vx = ((e.clientX - rect.left) / rect.width) * W;
    const frac = (vx - PAD.left) / (W - PAD.left - PAD.right);
    const idx = Math.round(frac * (points.length - 1));
    setHoverIdx(Math.max(0, Math.min(points.length - 1, idx)));
  };

  const strat = last.strategy;
  const bench = last.benchmark;
  // nudge the two end-labels apart when the series finish at a similar level
  let stratLabelY = y(strat);
  let benchLabelY = y(bench);
  if (Math.abs(stratLabelY - benchLabelY) < 13) {
    const mid = (stratLabelY + benchLabelY) / 2;
    stratLabelY = strat >= bench ? mid - 7 : mid + 7;
    benchLabelY = strat >= bench ? mid + 7 : mid - 7;
  }

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        role="img"
        aria-label={`Strategy equity versus ${benchmarkLabel} over the backtest window`}
        onMouseMove={onMove}
        onMouseLeave={() => setHoverIdx(null)}
        style={{ display: "block", overflow: "visible" }}
      >
        <defs>
          <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {gridVals.map((v, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--border)"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 6}
              y={y(v) + 3}
              fontSize={11}
              fill="var(--muted)"
              fontFamily="ui-monospace, monospace"
              textAnchor="end"
            >
              {money(v)}
            </text>
          </g>
        ))}

        {ticks.map((t) => (
          <text
            key={t.i}
            x={x(t.i)}
            y={H - 8}
            fontSize={11}
            fill="var(--muted)"
            textAnchor="middle"
          >
            {t.label}
          </text>
        ))}

        <path d={area} fill="url(#eq-fill)" />
        <path
          d={line("benchmark")}
          fill="none"
          stroke="var(--muted)"
          strokeWidth={2}
          strokeDasharray="5 4"
          strokeLinejoin="round"
        />
        <path
          d={line("strategy")}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* direct end-labels */}
        <text
          x={x(points.length - 1) + 6}
          y={stratLabelY + 3}
          fontSize={11}
          fontWeight={600}
          fill="var(--accent)"
        >
          Strategy
        </text>
        <text
          x={x(points.length - 1) + 6}
          y={benchLabelY + 3}
          fontSize={11}
          fill="var(--muted)"
        >
          {benchmarkLabel}
        </text>

        {hover && hoverIdx != null && (
          <g>
            <line
              x1={x(hoverIdx)}
              x2={x(hoverIdx)}
              y1={PAD.top}
              y2={H - PAD.bottom}
              stroke="var(--border-strong)"
              strokeWidth={1}
            />
            <circle
              cx={x(hoverIdx)}
              cy={y(hover.strategy)}
              r={3.5}
              fill="var(--accent)"
            />
            <circle
              cx={x(hoverIdx)}
              cy={y(hover.benchmark)}
              r={3.5}
              fill="var(--muted)"
            />
          </g>
        )}
      </svg>

      <figcaption className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 bg-[var(--accent)]" />
            Strategy
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-0 w-4 border-t-2 border-dashed"
              style={{ borderColor: "var(--muted)" }}
            />
            {benchmarkLabel}
          </span>
        </span>
        {hover ? (
          <span className="font-mono text-foreground/80">
            {hover.date} · strategy {money(hover.strategy)} ·{" "}
            {benchmarkLabel.toLowerCase()} {money(hover.benchmark)}
          </span>
        ) : (
          <span className="font-mono">
            hover for values · rebased to equal start capital
          </span>
        )}
      </figcaption>
    </figure>
  );
}
