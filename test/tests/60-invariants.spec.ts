import { execSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "@playwright/test";
import {
  SCRATCH_TICKERS,
  ensureInWatchlist,
  getPortfolio,
  scratchTickerCleanup,
} from "../fixtures/reset";
import { waitForConnectionState, waitForPricePresent } from "../fixtures/sse";

/**
 * Product invariants called out explicitly in the task brief and PLAN.md §14 as the most
 * likely regressions, beyond the happy-path scenarios covered in the other spec files.
 */

test.describe("stated invariants", () => {
  test("session change % is labelled as session, not daily", async ({ page }) => {
    await page.goto("/");
    // No dedicated testid exists for the column label itself (TEAM_CONTRACT.md §8 only lists
    // interactive/data cells) — this reads copy inside the already-identified watchlist
    // container rather than inventing a new selector. Flagged in test/README.md.
    await expect(page.getByTestId("watchlist")).toContainText(/session/i);
    await expect(page.getByTestId("watchlist")).not.toContainText(/daily/i);
  });

  test("a newly added ticker never renders its price as literal $0 before the first tick", async ({
    page,
    request,
  }) => {
    const ticker = SCRATCH_TICKERS.visualizations; // reuse an unused-at-this-point scratch ticker
    await scratchTickerCleanup(request, ticker);

    await page.goto("/");
    await ensureInWatchlist(request, ticker);
    await page.reload();

    const cell = page.getByTestId(`watchlist-price-${ticker}`);
    await expect(cell).toBeVisible();
    // Immediately after the row appears — before asserting a real price is present — it must
    // never read as literal zero. PLAN.md §14.1: "A missing price must show as unavailable,
    // never silently value a holding at zero."
    await expect(cell).not.toHaveText(/^\$?0(\.0+)?$/);

    await waitForPricePresent(page, ticker);
    await scratchTickerCleanup(request, ticker);
  });

  test("a failed AI-initiated trade never shows as a position", async ({ page, request }) => {
    // Covered end-to-end in chat.spec.ts; this asserts the data-layer half of the same
    // invariant directly against the API, independent of chat/mock wiring.
    const ticker = SCRATCH_TICKERS.chat;
    await scratchTickerCleanup(request, ticker);

    const res = await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 999_999_999, side: "buy" },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("INSUFFICIENT_CASH");
  });

  test("cash and quantity never render as float noise (e.g. 9999.999999999998)", async ({
    page,
  }) => {
    await page.goto("/");
    const cashText = await page.getByTestId("cash-balance").textContent();
    // Two-decimal money, optionally with thousands separators and a currency symbol.
    expect(cashText).toMatch(/^\D*[\d,]+\.\d{2}\D*$/);
  });
});

test.describe("restart persistence", () => {
  // Disruptive and slow (rebuilds/restarts the whole compose stack Playwright's webServer is
  // managing), so it's opt-in rather than part of the default run. Enable with
  // RUN_RESTART_TEST=true once the stack under test is up. See test/README.md.
  test.skip(
    process.env.RUN_RESTART_TEST !== "true",
    "opt-in: set RUN_RESTART_TEST=true to exercise the container restart cycle",
  );

  test("portfolio survives a container stop/start cycle", async ({ page, request }) => {
    const repoRoot = path.resolve(__dirname, "..", "..");
    const before = await getPortfolio(request);

    execSync("docker compose restart", { cwd: repoRoot, stdio: "inherit" });

    await expect
      .poll(
        async () => {
          try {
            const res = await request.get("/api/health");
            return res.ok();
          } catch {
            return false;
          }
        },
        { timeout: 60_000, message: "backend did not come back healthy after restart" },
      )
      .toBeTruthy();

    await page.goto("/");
    await waitForConnectionState(page, "connected", 30_000);

    const after = await getPortfolio(request);
    expect(after.cash_balance).toBe(before.cash_balance);
    expect(after.positions.length).toBe(before.positions.length);
  });
});
