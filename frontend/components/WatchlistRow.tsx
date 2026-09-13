"use client";

import { usePriceFlash } from "@/hooks/usePriceFlash";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { PriceUpdate } from "@/lib/types";
import { Sparkline } from "./Sparkline";

interface WatchlistRowProps {
  ticker: string;
  update: PriceUpdate | undefined;
  sparkline: number[];
  selected: boolean;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  removing: boolean;
}

const FLASH_CLASS: Record<"up" | "down", string> = {
  up: "animate-flash-up",
  down: "animate-flash-down",
};

export function WatchlistRow({ ticker, update, sparkline, selected, onSelect, onRemove, removing }: WatchlistRowProps) {
  const flash = usePriceFlash(update?.price);
  const changeColor = !update ? "text-ink-muted" : update.change_pct > 0 ? "text-good-text" : update.change_pct < 0 ? "text-critical-text" : "text-ink-secondary";

  return (
    <div
      data-testid={`watchlist-row-${ticker}`}
      data-selected={selected}
      onClick={() => onSelect(ticker)}
      className={`group flex cursor-pointer items-center gap-3 border-b border-line-subtle px-3 py-2 transition-colors hover:bg-base-raised ${
        selected ? "bg-base-raised" : ""
      }`}
    >
      <div className="w-14 shrink-0">
        <div className="font-mono text-[13px] font-semibold text-ink-primary">{ticker}</div>
      </div>

      <div className="w-24 shrink-0">
        <Sparkline data={sparkline} width={88} height={26} />
      </div>

      <div className={`flex-1 rounded px-1.5 py-0.5 text-right ${flash ? FLASH_CLASS[flash] : ""}`}>
        <div data-testid={`watchlist-price-${ticker}`} className="tnum font-mono text-[13px] text-ink-primary">
          {update ? formatCurrency(update.price) : "—"}
        </div>
        <div data-testid={`watchlist-change-${ticker}`} className={`tnum font-mono text-[11px] ${changeColor}`} title="Session change vs. today's open">
          {update ? formatPercent(update.change_pct, { signed: true }) : "—"}
        </div>
      </div>

      <button
        type="button"
        data-testid={`watchlist-remove-${ticker}`}
        onClick={(e) => {
          e.stopPropagation();
          onRemove(ticker);
        }}
        disabled={removing}
        aria-label={`Remove ${ticker} from watchlist`}
        className="shrink-0 rounded px-1.5 py-1 text-ink-muted opacity-0 transition-opacity hover:bg-critical/20 hover:text-critical-text group-hover:opacity-100 disabled:opacity-40"
      >
        ✕
      </button>
    </div>
  );
}
