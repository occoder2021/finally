import { expect, type APIRequestContext } from "@playwright/test";

/**
 * The backend is single-user with no reset endpoint (TEAM_CONTRACT.md §5-6 expose no
 * `/api/test/reset`), and the suite runs with `workers: 1` against one shared database. These
 * helpers keep specs independent of each other's leftover state without needing one:
 *  - use a scratch ticker outside the default 10-ticker seed for anything mutating,
 *  - assert deltas (cash decreased by X) rather than absolute totals,
 *  - clean up best-effort at the end of each spec (close positions, remove from watchlist).
 *
 * See test/README.md for the open question about whether a test-only reset endpoint, or a
 * documented `docker compose down -v` before CI runs, should be added instead.
 */

export const DEFAULT_WATCHLIST = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
] as const;

/** Tickers outside the default seed, used as scratch tickers by mutating specs so they never
 *  collide with each other or with the default watchlist fixtures other specs rely on. */
export const SCRATCH_TICKERS = {
  watchlist: "DIS",
  trading: "KO",
  visualizations: "PFE",
  chat: "XOM",
} as const;

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  pnl_percent: number | null;
  price_available: boolean;
}

export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  total_value: number;
  total_unrealized_pnl: number;
  starting_cash: number;
}

export async function getPortfolio(
  request: APIRequestContext,
): Promise<Portfolio> {
  const res = await request.get("/api/portfolio");
  expect(res.ok(), `GET /api/portfolio failed: ${res.status()}`).toBeTruthy();
  return res.json();
}

export async function getWatchlist(
  request: APIRequestContext,
): Promise<string[]> {
  const res = await request.get("/api/watchlist");
  expect(res.ok(), `GET /api/watchlist failed: ${res.status()}`).toBeTruthy();
  const body = await res.json();
  return body.tickers;
}

export async function ensureInWatchlist(
  request: APIRequestContext,
  ticker: string,
) {
  const tickers = await getWatchlist(request);
  if (!tickers.includes(ticker)) {
    const res = await request.post("/api/watchlist", { data: { ticker } });
    expect(res.ok(), `POST /api/watchlist(${ticker}) failed: ${res.status()}`).toBeTruthy();
  }
}

/** Best-effort: sell down any open position in `ticker` back to zero so tests don't leak state. */
export async function closePositionIfAny(
  request: APIRequestContext,
  ticker: string,
) {
  const portfolio = await getPortfolio(request);
  const position = portfolio.positions.find((p) => p.ticker === ticker);
  if (position && position.quantity > 0) {
    await request.post("/api/portfolio/trade", {
      data: { ticker, quantity: position.quantity, side: "sell" },
    });
  }
}

/** Best-effort: remove a ticker from the watchlist if present (no-op if it's still held —
 *  the backend intentionally refuses that, per TEAM_CONTRACT.md §6). */
export async function removeFromWatchlistIfPresent(
  request: APIRequestContext,
  ticker: string,
) {
  const tickers = await getWatchlist(request);
  if (tickers.includes(ticker)) {
    await request.delete(`/api/watchlist/${ticker}`);
  }
}

/** Full best-effort teardown for a scratch ticker: close any position, then remove it from the
 *  watchlist. Safe to call even if the spec never got that far. */
export async function scratchTickerCleanup(
  request: APIRequestContext,
  ticker: string,
) {
  await closePositionIfAny(request, ticker);
  await removeFromWatchlistIfPresent(request, ticker);
}
