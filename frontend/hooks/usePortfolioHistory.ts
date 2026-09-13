"use client";

import { useCallback, useEffect, useState } from "react";
import { getPortfolioHistory } from "@/lib/api";
import type { Snapshot } from "@/lib/types";

export interface PortfolioHistoryState {
  snapshots: Snapshot[];
  loading: boolean;
  refetch: () => Promise<void>;
}

export function usePortfolioHistory(): PortfolioHistoryState {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const data = await getPortfolioHistory();
      setSnapshots(data.snapshots);
    } catch {
      // Non-critical panel; leave the last-known snapshots on screen.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { snapshots, loading, refetch };
}
