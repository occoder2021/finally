"use client";

import { useCallback, useEffect, useState } from "react";
import { addToWatchlist, ApiError, getWatchlist, removeFromWatchlist } from "@/lib/api";

export interface WatchlistState {
  tickers: string[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  add: (ticker: string) => Promise<void>;
  remove: (ticker: string) => Promise<void>;
}

/** `GET /api/watchlist` returns tickers only — no prices, so there is exactly
 * one price source (SSE) and no stale-price flash on load (TEAM_CONTRACT §6). */
export function useWatchlist(): WatchlistState {
  const [tickers, setTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await getWatchlist();
      setTickers(data.tickers);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load watchlist.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const add = useCallback(
    async (ticker: string) => {
      await addToWatchlist(ticker);
      await refetch();
    },
    [refetch],
  );

  const remove = useCallback(
    async (ticker: string) => {
      await removeFromWatchlist(ticker);
      await refetch();
    },
    [refetch],
  );

  return { tickers, loading, error, refetch, add, remove };
}
