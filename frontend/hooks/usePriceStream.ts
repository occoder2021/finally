"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionState, PriceFrame } from "@/lib/types";

const SPARKLINE_MAX_POINTS = 180;

export interface PriceStreamState {
  prices: PriceFrame;
  connectionState: ConnectionState;
  /** Per-ticker price series accumulated client-side since page load, for
   * the watchlist sparklines. Progressive — starts empty, fills over time. */
  sparklines: Record<string, number[]>;
}

/**
 * Owns the single `EventSource` connection to `/api/stream/prices`.
 * The server pushes a full cache snapshot immediately on every connect,
 * including reconnects, so this never needs to poll or merge partial state
 * across a reconnect — each frame simply overwrites the tickers it carries.
 */
export function usePriceStream(): PriceStreamState {
  const [prices, setPrices] = useState<PriceFrame>({});
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/stream/prices");
    esRef.current = es;

    const handleOpen = () => setConnectionState("connected");

    const handleError = () => {
      setConnectionState(es.readyState === EventSource.CLOSED ? "disconnected" : "connecting");
    };

    const handleMessage = (ev: MessageEvent<string>) => {
      let frame: PriceFrame;
      try {
        frame = JSON.parse(ev.data) as PriceFrame;
      } catch {
        return;
      }
      setPrices((prev) => ({ ...prev, ...frame }));
      setSparklines((prev) => {
        const next = { ...prev };
        for (const [ticker, update] of Object.entries(frame)) {
          const series = next[ticker] ?? [];
          const appended = series.length >= SPARKLINE_MAX_POINTS
            ? [...series.slice(series.length - SPARKLINE_MAX_POINTS + 1), update.price]
            : [...series, update.price];
          next[ticker] = appended;
        }
        return next;
      });
    };

    es.addEventListener("open", handleOpen);
    es.addEventListener("error", handleError);
    es.addEventListener("message", handleMessage);

    return () => {
      es.removeEventListener("open", handleOpen);
      es.removeEventListener("error", handleError);
      es.removeEventListener("message", handleMessage);
      es.close();
      esRef.current = null;
    };
  }, []);

  return { prices, connectionState, sparklines };
}
