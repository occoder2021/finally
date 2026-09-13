"use client";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
}

/**
 * Minimal inline-SVG mini chart, accumulated client-side from the SSE stream
 * since page load (PLAN.md §2/§10 — it fills in progressively, never
 * pre-seeded). Thin 2px line per the dataviz mark spec; colored by net
 * direction over the visible window, never used as the sole signal (the
 * price cell beside it always carries the numeric value + sign).
 */
export function Sparkline({ data, width = 96, height = 28 }: SparklineProps) {
  if (data.length < 2) {
    return (
      <svg width={width} height={height} aria-hidden="true" className="text-ink-muted">
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="currentColor" strokeWidth={1} strokeDasharray="2 3" />
      </svg>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = width / (data.length - 1);
  const pad = 2;

  const points = data
    .map((v, i) => {
      const x = i * stepX;
      const y = pad + (1 - (v - min) / span) * (height - pad * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const rising = data[data.length - 1]! >= data[0]!;
  const stroke = rising ? "#17c964" : "#e5484d";

  return (
    <svg width={width} height={height} aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
