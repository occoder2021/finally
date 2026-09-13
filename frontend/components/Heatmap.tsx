"use client";

import { ResponsiveContainer, Tooltip, Treemap } from "recharts";
import { formatCurrency, formatPercent } from "@/lib/format";
import { pnlColor } from "@/lib/colorScale";
import type { LivePosition } from "@/lib/portfolio";

interface HeatmapProps {
  positions: LivePosition[];
}

interface TreemapDatum {
  name: string;
  size: number;
  pnlPercent: number;
  pnlAbs: number;
  marketValue: number;
}

/**
 * Treemap sized by portfolio weight, colored by P&L (PLAN.md §10). Only
 * priced positions can be sized meaningfully; a position with no live price
 * is listed underneath instead of silently disappearing (it still needs a
 * size for the algorithm to place it, which an unpriced holding doesn't have).
 */
export function Heatmap({ positions }: HeatmapProps) {
  const priced = positions.filter((p) => p.price_available && (p.market_value ?? 0) > 0);
  const unpriced = positions.filter((p) => !p.price_available);

  const data: TreemapDatum[] = priced.map((p) => ({
    name: p.ticker,
    size: p.market_value!,
    pnlPercent: p.pnl_percent ?? 0,
    pnlAbs: p.unrealized_pnl ?? 0,
    marketValue: p.market_value!,
  }));

  return (
    <section data-testid="heatmap" className="flex h-full flex-col">
      <h2 className="px-3 pb-2 pt-3 text-[13px] font-semibold text-ink-primary">Portfolio heatmap</h2>
      <div className="min-h-0 flex-1 px-2 pb-2">
        {data.length === 0 ? (
          <div className="grid h-full place-items-center text-[12px] text-ink-muted">
            No priced positions to show yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap data={data} dataKey="size" stroke="#0d1117" content={<HeatmapCell />} isAnimationActive={false}>
              <Tooltip content={<HeatmapTooltip />} />
            </Treemap>
          </ResponsiveContainer>
        )}
        {unpriced.length > 0 && (
          <p className="pt-1 text-[11px] text-ink-muted">
            Unavailable: {unpriced.map((p) => p.ticker).join(", ")}
          </p>
        )}
      </div>
    </section>
  );
}

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPercent?: number;
}

function HeatmapCell(props: CellProps) {
  const { x = 0, y = 0, width = 0, height = 0, name, pnlPercent = 0 } = props;
  if (width <= 0 || height <= 0) return null;
  const fill = pnlColor(pnlPercent);
  const showLabel = width > 44 && height > 24;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} stroke="#0d1117" strokeWidth={2} rx={2} />
      {showLabel && (
        <>
          <text x={x + 6} y={y + 16} fontSize={11} fontFamily="var(--font-data)" fontWeight={600} fill="#0d1117">
            {name}
          </text>
          {height > 40 && (
            <text x={x + 6} y={y + 30} fontSize={10} fontFamily="var(--font-data)" fill="#0d1117" opacity={0.85}>
              {formatPercent(pnlPercent, { signed: true })}
            </text>
          )}
        </>
      )}
    </g>
  );
}

function HeatmapTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: TreemapDatum }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]!.payload;
  return (
    <div className="rounded border border-line bg-base-overlay px-2.5 py-1.5 text-[11px] shadow-lg">
      <div className="font-mono font-semibold text-ink-primary">{d.name}</div>
      <div className="tnum text-ink-secondary">{formatCurrency(d.marketValue)}</div>
      <div className={`tnum ${d.pnlAbs >= 0 ? "text-good-text" : "text-critical-text"}`}>
        {formatPercent(d.pnlPercent, { signed: true })}
      </div>
    </div>
  );
}
