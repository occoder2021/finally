import { test, expect } from "@playwright/test";
import {
  SCRATCH_TICKERS,
  ensureInWatchlist,
  scratchTickerCleanup,
} from "../fixtures/reset";
import { parseMoney } from "../fixtures/money";
import { waitForPricePresent } from "../fixtures/sse";

const TICKER = SCRATCH_TICKERS.trading;
const QUANTITY = "1";

test.describe("buy and sell", () => {
  test.beforeEach(async ({ page, request }) => {
    await ensureInWatchlist(request, TICKER);
    await page.goto("/");
    await waitForPricePresent(page, TICKER);
  });

  test.afterEach(async ({ request }) => {
    await scratchTickerCleanup(request, TICKER);
  });

  test("buying shares decreases cash and adds a position", async ({ page }) => {
    const cashBefore = parseMoney(await page.getByTestId("cash-balance").textContent());

    await page.getByTestId("trade-ticker").fill(TICKER);
    await page.getByTestId("trade-quantity").fill(QUANTITY);
    await expect(page.getByTestId("trade-estimate")).toHaveText(/\d/);

    await page.getByTestId("trade-buy").click();

    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
    await expect(page.getByTestId(`position-qty-${TICKER}`)).toHaveText(/1/);

    await expect
      .poll(async () => parseMoney(await page.getByTestId("cash-balance").textContent()), {
        message: "cash balance did not decrease after a buy",
      })
      .toBeLessThan(cashBefore);
  });

  test("selling the full position removes the row and increases cash", async ({ page }) => {
    // Arrange: buy first so there is something to fully close.
    await page.getByTestId("trade-ticker").fill(TICKER);
    await page.getByTestId("trade-quantity").fill(QUANTITY);
    await page.getByTestId("trade-buy").click();
    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();

    const cashBefore = parseMoney(await page.getByTestId("cash-balance").textContent());
    const qtyText = await page.getByTestId(`position-qty-${TICKER}`).textContent();
    const qty = qtyText!.replace(/[^0-9.\-]/g, "");

    await page.getByTestId("trade-ticker").fill(TICKER);
    await page.getByTestId("trade-quantity").fill(qty);
    await page.getByTestId("trade-sell").click();

    // Full close: the row is deleted, not left at quantity 0 (PLAN.md §7 / TEAM_CONTRACT.md §3).
    await expect(page.getByTestId(`position-row-${TICKER}`)).toHaveCount(0);

    await expect
      .poll(async () => parseMoney(await page.getByTestId("cash-balance").textContent()), {
        message: "cash balance did not increase after a full sell",
      })
      .toBeGreaterThan(cashBefore);
  });

  test("selling more shares than held is rejected with a readable error", async ({ page }) => {
    await page.getByTestId("trade-ticker").fill(TICKER);
    await page.getByTestId("trade-quantity").fill("999999");
    await page.getByTestId("trade-sell").click();

    await expect(page.getByTestId("trade-error")).toBeVisible();
    await expect(page.getByTestId(`position-row-${TICKER}`)).toHaveCount(0);
  });

  test("buying with a non-positive quantity is rejected client-side or by the API", async ({
    page,
  }) => {
    await page.getByTestId("trade-ticker").fill(TICKER);
    await page.getByTestId("trade-quantity").fill("0");
    await page.getByTestId("trade-buy").click();

    await expect(page.getByTestId(`position-row-${TICKER}`)).toHaveCount(0);
  });
});
