import { test, expect } from "@playwright/test";
import { DEFAULT_WATCHLIST, getPortfolio, getWatchlist } from "../fixtures/reset";
import { looksNumeric, parseMoney } from "../fixtures/money";
import { waitForConnectionState, waitForPriceChange } from "../fixtures/sse";

/**
 * PLAN.md §12: "Fresh start: default watchlist appears, $10k balance shown, prices are
 * streaming."
 *
 * `playwright.config.ts`'s `webServer.command` runs `docker compose -p finally-e2e down -v`
 * before `up --build`, against the isolated `finally-e2e-data` volume (never the default
 * project's real `finally-data`) — so the database is guaranteed freshly-seeded at the start
 * of every `npm test` run, by default (`E2E_REUSE=true` opts out for faster local iteration,
 * at the cost of this file's exact-$10,000 assertion no longer holding — see test/README.md).
 *
 * This file's numeric `00-` prefix is deliberate: with `workers: 1` and `fullyParallel:
 * false`, Playwright runs spec files in filesystem-sorted order, and this suite's other specs
 * mutate cash/positions/watchlist. The exact-freshness assertions below must run before any
 * of that happens, which only holds if this file runs first.
 */

test.describe("fresh start", () => {
  test("default watchlist, cash balance, and connection all render", async ({ page }) => {
    await page.goto("/");

    await waitForConnectionState(page, "connected");

    const tickers = await getWatchlist(page.request);
    for (const ticker of DEFAULT_WATCHLIST) {
      expect(tickers, `expected default ticker ${ticker} in watchlist`).toContain(ticker);
    }
    for (const ticker of DEFAULT_WATCHLIST) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }

    const cashText = await page.getByTestId("cash-balance").textContent();
    expect(looksNumeric(cashText)).toBeTruthy();
    expect(parseMoney(cashText)).toBeGreaterThanOrEqual(0);

    const totalText = await page.getByTestId("total-value").textContent();
    expect(looksNumeric(totalText)).toBeTruthy();

    const returnText = await page.getByTestId("total-return").textContent();
    expect(returnText).not.toBeNull();
  });

  test("prices are actually streaming (not a static snapshot)", async ({ page }) => {
    await page.goto("/");
    await waitForConnectionState(page, "connected");

    // AAPL is always in the default watchlist and always tracked, so its price should tick
    // within a generous window regardless of which other specs ran first.
    await waitForPriceChange(page, "AAPL", 20_000);
  });

  test("cash balance is exactly the $10,000 seed on a fresh database", async ({ page }) => {
    test.skip(
      process.env.E2E_REUSE === "true",
      "E2E_REUSE=true reuses a stack across runs, so the DB is no longer guaranteed fresh",
    );
    const portfolio = await getPortfolio(page.request);
    expect(portfolio.cash_balance).toBe(10_000);
    expect(portfolio.total_value).toBe(10_000);
    expect(portfolio.positions).toEqual([]);
  });

  test("starting_cash baseline is always $10,000 regardless of trading activity", async ({
    page,
  }) => {
    const portfolio = await getPortfolio(page.request);
    expect(portfolio.starting_cash).toBe(10_000);
  });
});
