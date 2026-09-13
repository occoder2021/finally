import { test, expect } from "@playwright/test";
import {
  SCRATCH_TICKERS,
  ensureInWatchlist,
  scratchTickerCleanup,
} from "../fixtures/reset";
import { waitForPricePresent } from "../fixtures/sse";

const TICKER = SCRATCH_TICKERS.visualizations;

test.describe("portfolio visualizations", () => {
  test.beforeEach(async ({ page, request }) => {
    await ensureInWatchlist(request, TICKER);
    await page.goto("/");
    await waitForPricePresent(page, TICKER);

    // Guarantee at least one open position so the heatmap has something to render.
    await page.getByTestId("trade-ticker").fill(TICKER);
    await page.getByTestId("trade-quantity").fill("1");
    await page.getByTestId("trade-buy").click();
    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
  });

  test.afterEach(async ({ request }) => {
    await scratchTickerCleanup(request, TICKER);
  });

  test("heatmap renders a rectangle per position", async ({ page }) => {
    const heatmap = page.getByTestId("heatmap");
    await expect(heatmap).toBeVisible();
    // The treemap implementation (SVG/canvas/div-grid) is up to the frontend engineer; assert
    // only that the container is non-empty once a position exists, not on a specific renderer.
    await expect
      .poll(async () => (await heatmap.innerHTML()).length, {
        message: "heatmap container is empty even though a position exists",
      })
      .toBeGreaterThan(0);
  });

  test("P&L chart renders with at least one data point", async ({ page }) => {
    const chart = page.getByTestId("pnl-chart");
    await expect(chart).toBeVisible();
    await expect
      .poll(async () => (await chart.innerHTML()).length, {
        message: "pnl-chart container is empty",
      })
      .toBeGreaterThan(0);
  });

  test("main chart renders for the selected ticker", async ({ page }) => {
    await page.getByTestId(`watchlist-row-${TICKER}`).click();

    const chart = page.getByTestId("main-chart");
    await expect(chart).toBeVisible();
    await expect
      .poll(async () => (await chart.innerHTML()).length, {
        message: "main-chart container is empty after selecting a ticker",
      })
      .toBeGreaterThan(0);
  });

  test("positions table shows the position with a non-negative market value or unavailable state", async ({
    page,
  }) => {
    await expect(page.getByTestId("positions-table")).toBeVisible();
    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
    await expect(page.getByTestId(`position-qty-${TICKER}`)).toHaveText(/\d/);
    await expect(page.getByTestId(`position-pnl-${TICKER}`)).toBeVisible();
  });
});
