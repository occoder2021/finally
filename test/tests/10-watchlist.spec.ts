import { test, expect } from "@playwright/test";
import { SCRATCH_TICKERS, removeFromWatchlistIfPresent } from "../fixtures/reset";

const TICKER = SCRATCH_TICKERS.watchlist;

test.describe("watchlist add/remove", () => {
  test.beforeEach(async ({ request }) => {
    await removeFromWatchlistIfPresent(request, TICKER);
  });

  test.afterEach(async ({ request }) => {
    await removeFromWatchlistIfPresent(request, TICKER);
  });

  test("adding a ticker via the UI shows it in the watchlist", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId(`watchlist-row-${TICKER}`)).toHaveCount(0);

    await page.getByTestId("watchlist-add-input").fill(TICKER);
    await page.getByTestId("watchlist-add-submit").click();

    await expect(page.getByTestId(`watchlist-row-${TICKER}`)).toBeVisible();
    await expect(page.getByTestId(`watchlist-price-${TICKER}`)).toBeVisible();
    await expect(page.getByTestId(`watchlist-change-${TICKER}`)).toBeVisible();
  });

  test("removing a ticker via the UI drops it from the watchlist", async ({ page, request }) => {
    await page.goto("/");
    await page.getByTestId("watchlist-add-input").fill(TICKER);
    await page.getByTestId("watchlist-add-submit").click();
    await expect(page.getByTestId(`watchlist-row-${TICKER}`)).toBeVisible();

    await page.getByTestId(`watchlist-remove-${TICKER}`).click();

    await expect(page.getByTestId(`watchlist-row-${TICKER}`)).toHaveCount(0);

    const res = await request.get("/api/watchlist");
    const body = await res.json();
    expect(body.tickers).not.toContain(TICKER);
  });

  test("adding a duplicate ticker surfaces a readable error and does not duplicate the row", async ({
    page,
  }) => {
    await page.goto("/");

    await page.getByTestId("watchlist-add-input").fill("AAPL");
    await page.getByTestId("watchlist-add-submit").click();

    await expect(page.getByTestId("watchlist-error")).toBeVisible();
    await expect(page.getByTestId("watchlist-error")).toHaveText(/\S/);
    await expect(page.getByTestId(`watchlist-row-AAPL`)).toHaveCount(1);
  });

  test("adding a malformed ticker surfaces a readable error and adds nothing", async ({
    page,
  }) => {
    await page.goto("/");

    await page.getByTestId("watchlist-add-input").fill("12345");
    await page.getByTestId("watchlist-add-submit").click();

    await expect(page.getByTestId("watchlist-error")).toBeVisible();
    await expect(page.getByTestId("watchlist-error")).toHaveText(/\S/);
    await expect(page.getByTestId(`watchlist-row-12345`)).toHaveCount(0);
  });
});
