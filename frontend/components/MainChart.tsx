"use client";

import { ColorType, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { getPriceHistory } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { PriceUpdate } from "@/lib/types";

interface MainChartProps {
  ticker: string | null;
  latestUpdate: PriceUpdate | undefined;
}

function toUnixSeconds(ts: number): UTCTimestamp {
  return Math.floor(ts) as UTCTimestamp;
}

/**
 * Seeds from `GET /api/prices/{ticker}/history` on selection, then appends
 * live points as SSE frames arrive for the selected ticker — no polling
 * (TEAM_CONTRACT §8, PLAN Q3-adjacent behaviour). A brand-new ticker with no
 * recorded history yet starts empty and fills in live.
 */
export function MainChart({ ticker, latestUpdate }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const lastTimeRef = useRef<number>(0);
  const [empty, setEmpty] = useState(true);

  // Create the chart once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8d95ab",
        fontFamily: "var(--font-data), ui-monospace, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1a2030" },
        horzLines: { color: "#1a2030" },
      },
      rightPriceScale: { borderColor: "#232a3b" },
      timeScale: { borderColor: "#232a3b", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
      autoSize: true,
    });
    const series = chart.addLineSeries({
      color: "#209dd7",
      lineWidth: 2,
      priceLineVisible: true,
      lastValueVisible: true,
    });
    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Seed history whenever the selected ticker changes.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !ticker) return;

    let cancelled = false;
    series.setData([]);
    lastTimeRef.current = 0;
    setEmpty(true);

    getPriceHistory(ticker)
      .then((res) => {
        if (cancelled) return;
        const seen = new Set<number>();
        const points = res.points
          .map((p) => ({ time: toUnixSeconds(p.timestamp), value: p.price }))
          .filter((p) => {
            if (seen.has(p.time)) return false;
            seen.add(p.time);
            return true;
          })
          .sort((a, b) => a.time - b.time);
        series.setData(points);
        if (points.length > 0) {
          lastTimeRef.current = points[points.length - 1]!.time;
          setEmpty(false);
        }
        chartRef.current?.timeScale().fitContent();
      })
      .catch(() => {
        // History absent for a brand-new ticker is expected; live points
        // (below) fill the chart in from here.
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  // Append live points for the selected ticker.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !ticker || !latestUpdate || latestUpdate.ticker !== ticker) return;

    const time = toUnixSeconds(latestUpdate.timestamp);
    if (time < lastTimeRef.current) return; // out-of-order frame, ignore
    if (time === lastTimeRef.current) {
      series.update({ time, value: latestUpdate.price });
      return;
    }
    lastTimeRef.current = time;
    series.update({ time, value: latestUpdate.price });
    setEmpty(false);
  }, [ticker, latestUpdate]);

  return (
    <div data-testid="main-chart" className="relative flex h-full flex-col">
      <div className="flex items-baseline gap-3 px-3 pt-2">
        <h2 className="font-mono text-[14px] font-semibold text-ink-primary">{ticker ?? "Select a ticker"}</h2>
        {latestUpdate && (
          <>
            <span className="tnum font-mono text-[13px] text-ink-primary">{formatCurrency(latestUpdate.price)}</span>
            <span
              className={`tnum font-mono text-[12px] ${
                latestUpdate.change_pct > 0 ? "text-good-text" : latestUpdate.change_pct < 0 ? "text-critical-text" : "text-ink-secondary"
              }`}
            >
              {formatPercent(latestUpdate.change_pct, { signed: true })} session
            </span>
          </>
        )}
      </div>
      <div className="relative min-h-0 flex-1 px-1 pb-1">
        {!ticker && (
          <div className="absolute inset-0 grid place-items-center text-[12px] text-ink-muted">
            Pick a ticker from the watchlist to see its chart.
          </div>
        )}
        {ticker && empty && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-[12px] text-ink-muted">
            Waiting for price data…
          </div>
        )}
        <div ref={containerRef} className="h-full w-full" />
      </div>
    </div>
  );
}
