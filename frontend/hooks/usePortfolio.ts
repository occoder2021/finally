"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getPortfolio } from "@/lib/api";
import type { PortfolioResponse } from "@/lib/types";

export interface PortfolioState {
  portfolio: PortfolioResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * REST is the source of truth for cash, quantity and avg_cost (division of
 * truth, TEAM_CONTRACT §8). This hook only fetches that snapshot; live
 * valuation is recomputed from SSE prices by `computeLiveValuation`
 * (lib/portfolio.ts), not by polling this endpoint. Callers refetch()
 * explicitly after any manual or AI-initiated action.
 */
export function usePortfolio(): PortfolioState {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await getPortfolio();
      setPortfolio(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load portfolio.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { portfolio, loading, error, refetch };
}
