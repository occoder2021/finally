import { describe, expect, it } from "vitest";
import { computeLiveValuation } from "@/lib/portfolio";
import { mockPortfolio, mockPrices } from "@/lib/fixtures";
import type { PriceFrame } from "@/lib/types";

describe("computeLiveValuation", () => {
  it("returns an empty valuation when portfolio hasn't loaded", () => {
    const result = computeLiveValuation(null, {});
    expect(result).toEqual({ positions: [], totalValue: 0, totalUnrealizedPnl: 0, hasUnavailable: false });
  });

  it("recomputes market value and P&L from live SSE prices, not the REST snapshot", () => {
    // REST said AAPL was $191.50; a live tick moves it to $200 — the client
    // must use the live price, per the division-of-truth rule.
    const livePrices: PriceFrame = {
      AAPL: { ...mockPrices.AAPL!, price: 200 },
    };
    const result = computeLiveValuation(mockPortfolio, livePrices);
    const aapl = result.positions.find((p) => p.ticker === "AAPL")!;

    expect(aapl.current_price).toBe(200);
    expect(aapl.market_value).toBe(2000); // 10 shares * $200
    expect(aapl.unrealized_pnl).toBeCloseTo(100); // (200 - 190) * 10
    expect(aapl.isLive).toBe(true);
    expect(result.totalValue).toBe(mockPortfolio.cash_balance + 2000);
    expect(result.hasUnavailable).toBe(false);
  });

  it("falls back to the REST snapshot price when SSE hasn't reported that ticker yet", () => {
    const result = computeLiveValuation(mockPortfolio, {});
    const aapl = result.positions.find((p) => p.ticker === "AAPL")!;
    expect(aapl.current_price).toBe(mockPortfolio.positions[0]!.current_price);
    expect(aapl.isLive).toBe(false);
  });

  it("marks a position unavailable (never $0) when no price exists anywhere", () => {
    const portfolioWithGap = {
      ...mockPortfolio,
      positions: [{ ...mockPortfolio.positions[0]!, current_price: null }],
    };
    const result = computeLiveValuation(portfolioWithGap, {});
    const aapl = result.positions[0]!;
    expect(aapl.price_available).toBe(false);
    expect(aapl.current_price).toBeNull();
    expect(aapl.market_value).toBeNull();
    expect(result.hasUnavailable).toBe(true);
    // Unavailable position contributes 0, but cash still counts toward the total.
    expect(result.totalValue).toBe(mockPortfolio.cash_balance);
  });
});
