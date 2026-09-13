"use client";

import { usePriceFlash } from "@/hooks/usePriceFlash";
import { formatCurrency, formatPercent, formatQuantity, formatSignedCurrency } from "@/lib/format";
import type { LivePosition } from "@/lib/portfolio";

interface PositionsTableProps {
  positions: LivePosition[];
  onSelect: (ticker: string) => void;
}

export function PositionsTable({ positions, onSelect }: PositionsTableProps) {
  return (
    <section className="flex h-full flex-col">
      <h2 className="px-3 pb-2 pt-3 text-[13px] font-semibold text-ink-primary">Positions</h2>
      <div className="scroll-thin flex-1 overflow-auto">
        <table data-testid="positions-table" className="w-full border-collapse text-[12px]">
          <thead className="sticky top-0 bg-base-panel text-ink-muted">
            <tr className="text-left">
              <th className="px-3 py-1.5 font-normal">Ticker</th>
              <th className="px-3 py-1.5 font-normal text-right">Qty</th>
              <th className="px-3 py-1.5 font-normal text-right">Avg cost</th>
              <th className="px-3 py-1.5 font-normal text-right">Price</th>
              <th className="px-3 py-1.5 font-normal text-right">Mkt value</th>
              <th className="px-3 py-1.5 font-normal text-right">Unrealized P&amp;L</th>
              <th className="px-3 py-1.5 font-normal text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-ink-muted">
                  No open positions. Buy something from the trade bar to get started.
                </td>
              </tr>
            )}
            {positions.map((pos) => (
              <PositionRow key={pos.ticker} position={pos} onSelect={onSelect} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PositionRow({ position, onSelect }: { position: LivePosition; onSelect: (ticker: string) => void }) {
  const flash = usePriceFlash(position.current_price);
  const pnlColor = !position.price_available
    ? "text-ink-muted"
    : (position.unrealized_pnl ?? 0) > 0
      ? "text-good-text"
      : (position.unrealized_pnl ?? 0) < 0
        ? "text-critical-text"
        : "text-ink-secondary";

  return (
    <tr
      data-testid={`position-row-${position.ticker}`}
      onClick={() => onSelect(position.ticker)}
      className="cursor-pointer border-t border-line-subtle hover:bg-base-raised"
    >
      <td className="px-3 py-1.5 font-mono font-semibold text-ink-primary">{position.ticker}</td>
      <td data-testid={`position-qty-${position.ticker}`} className="tnum px-3 py-1.5 text-right font-mono text-ink-primary">
        {formatQuantity(position.quantity)}
      </td>
      <td className="tnum px-3 py-1.5 text-right font-mono text-ink-secondary">{formatCurrency(position.avg_cost)}</td>
      <td className={`tnum px-3 py-1.5 text-right font-mono text-ink-primary ${flash ? (flash === "up" ? "animate-flash-up" : "animate-flash-down") : ""}`}>
        {position.price_available ? formatCurrency(position.current_price!) : <span className="text-ink-muted" title="No live price available">unavailable</span>}
      </td>
      <td className="tnum px-3 py-1.5 text-right font-mono text-ink-primary">
        {position.price_available ? formatCurrency(position.market_value!) : "—"}
      </td>
      <td data-testid={`position-pnl-${position.ticker}`} className={`tnum px-3 py-1.5 text-right font-mono ${pnlColor}`}>
        {position.price_available ? formatSignedCurrency(position.unrealized_pnl!) : "—"}
      </td>
      <td className={`tnum px-3 py-1.5 text-right font-mono ${pnlColor}`}>
        {position.price_available ? formatPercent(position.pnl_percent!, { signed: true }) : "—"}
      </td>
    </tr>
  );
}
