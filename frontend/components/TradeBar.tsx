"use client";

import { useEffect, useState } from "react";
import { ApiError, postTrade } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import type { PriceFrame, TradeSide } from "@/lib/types";

interface TradeBarProps {
  selectedTicker: string | null;
  prices: PriceFrame;
  onTraded: () => void;
}

export function TradeBar({ selectedTicker, prices, onTraded }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker ?? "");
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<TradeSide | null>(null);
  const [lastFill, setLastFill] = useState<string | null>(null);

  useEffect(() => {
    if (selectedTicker) setTicker(selectedTicker);
  }, [selectedTicker]);

  const normalizedTicker = ticker.trim().toUpperCase();
  const qtyNum = Number(quantity);
  const qtyValid = quantity.trim() !== "" && Number.isFinite(qtyNum) && qtyNum > 0;
  const price = normalizedTicker ? prices[normalizedTicker]?.price : undefined;
  const estimate = qtyValid && price !== undefined ? qtyNum * price : null;

  async function submit(side: TradeSide) {
    if (!normalizedTicker || !qtyValid) {
      setError("Enter a ticker and a positive quantity.");
      return;
    }
    setPending(side);
    setError(null);
    setLastFill(null);
    try {
      const res = await postTrade(normalizedTicker, qtyNum, side);
      setLastFill(
        `${side === "buy" ? "Bought" : "Sold"} ${res.trade.quantity} ${res.trade.ticker} at ${formatCurrency(res.trade.price)}.`,
      );
      setQuantity("");
      onTraded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Trade failed.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3 border-t border-line bg-base-panel px-3 py-2.5">
      <Field label="Ticker">
        <input
          data-testid="trade-ticker"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          maxLength={5}
          placeholder="AAPL"
          className="w-24 rounded border border-line bg-base-raised px-2 py-1.5 font-mono text-[13px] uppercase text-ink-primary placeholder:text-ink-muted placeholder:normal-case focus:border-blue focus:outline-none"
        />
      </Field>

      <Field label="Quantity">
        <input
          data-testid="trade-quantity"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          inputMode="decimal"
          placeholder="0"
          className="w-24 rounded border border-line bg-base-raised px-2 py-1.5 text-right font-mono text-[13px] text-ink-primary placeholder:text-ink-muted focus:border-blue focus:outline-none"
        />
      </Field>

      <Field label="Estimate">
        <div data-testid="trade-estimate" className="tnum flex h-[34px] min-w-[110px] items-center rounded border border-line-subtle bg-base-plane px-2.5 font-mono text-[13px] text-ink-secondary">
          {estimate !== null ? formatCurrency(estimate) : qtyValid ? "Price unavailable" : "—"}
        </div>
      </Field>

      <button
        type="button"
        data-testid="trade-buy"
        onClick={() => submit("buy")}
        disabled={pending !== null}
        className="rounded bg-good px-4 py-1.5 text-[13px] font-semibold text-base-plane transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {pending === "buy" ? "Buying…" : "Buy"}
      </button>
      <button
        type="button"
        data-testid="trade-sell"
        onClick={() => submit("sell")}
        disabled={pending !== null}
        className="rounded bg-critical px-4 py-1.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {pending === "sell" ? "Selling…" : "Sell"}
      </button>

      <div className="min-w-0 flex-1">
        {error && (
          <p data-testid="trade-error" className="text-[12px] text-critical-text">
            {error}
          </p>
        )}
        {!error && lastFill && <p className="text-[12px] text-good-text">{lastFill}</p>}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10.5px] text-ink-muted">{label}</span>
      {children}
    </label>
  );
}
