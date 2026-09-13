"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { PriceFrame } from "@/lib/types";
import { WatchlistRow } from "./WatchlistRow";

interface WatchlistProps {
  tickers: string[];
  prices: PriceFrame;
  sparklines: Record<string, number[]>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

export function Watchlist({ tickers, prices, sparklines, selectedTicker, onSelect, onAdd, onRemove }: WatchlistProps) {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [removingTicker, setRemovingTicker] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const ticker = input.trim();
    if (!ticker) return;
    setSubmitting(true);
    setError(null);
    try {
      await onAdd(ticker);
      setInput("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add that ticker.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(ticker: string) {
    setRemovingTicker(ticker);
    setError(null);
    try {
      await onRemove(ticker);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not remove ${ticker}.`);
    } finally {
      setRemovingTicker(null);
    }
  }

  return (
    <section data-testid="watchlist" className="flex h-full flex-col">
      <div className="flex items-center justify-between px-3 pb-2 pt-3">
        <h2 className="text-[13px] font-semibold text-ink-primary">Watchlist</h2>
        <span className="text-[11px] text-ink-muted">{tickers.length}/25</span>
      </div>

      <form onSubmit={handleAdd} className="flex gap-1.5 px-3 pb-2">
        <input
          data-testid="watchlist-add-input"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          placeholder="Add ticker…"
          maxLength={5}
          className="w-full rounded border border-line bg-base-raised px-2 py-1 text-[12px] font-mono uppercase text-ink-primary placeholder:text-ink-muted placeholder:normal-case focus:border-blue focus:outline-none"
        />
        <button
          type="submit"
          data-testid="watchlist-add-submit"
          disabled={submitting || !input.trim()}
          className="shrink-0 rounded bg-purple px-3 py-1 text-[12px] font-medium text-white transition-colors hover:bg-purple-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          Add
        </button>
      </form>

      {error && (
        <p data-testid="watchlist-error" className="px-3 pb-2 text-[11px] text-critical-text">
          {error}
        </p>
      )}

      <div className="scroll-thin flex-1 overflow-y-auto">
        {tickers.length === 0 && (
          <p className="px-3 py-6 text-center text-[12px] text-ink-muted">No tickers yet — add one above.</p>
        )}
        {tickers.map((ticker) => (
          <WatchlistRow
            key={ticker}
            ticker={ticker}
            update={prices[ticker]}
            sparkline={sparklines[ticker] ?? []}
            selected={ticker === selectedTicker}
            onSelect={onSelect}
            onRemove={handleRemove}
            removing={removingTicker === ticker}
          />
        ))}
      </div>
    </section>
  );
}
