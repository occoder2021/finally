import { expect, type Page } from "@playwright/test";

/**
 * Helpers for asserting on the live SSE price stream and the connection-status dot
 * (`data-testid="connection-status"`, `data-state` = connected | connecting | disconnected —
 * TEAM_CONTRACT.md §8).
 */

export type ConnectionState = "connected" | "connecting" | "disconnected";

export async function waitForConnectionState(
  page: Page,
  state: ConnectionState,
  timeoutMs = 15_000,
) {
  await expect(page.getByTestId("connection-status")).toHaveAttribute(
    "data-state",
    state,
    { timeout: timeoutMs },
  );
}

/** Wait until a watchlist price cell renders a numeric value (i.e. not a dash/unavailable placeholder). */
export async function waitForPricePresent(
  page: Page,
  ticker: string,
  timeoutMs = 20_000,
) {
  await expect(page.getByTestId(`watchlist-price-${ticker}`)).toHaveText(
    /\d/,
    { timeout: timeoutMs },
  );
}

/**
 * Wait until a watchlist price cell's text changes at least once — proof the SSE stream is
 * actually pushing updates, not just rendering a static initial snapshot.
 */
export async function waitForPriceChange(
  page: Page,
  ticker: string,
  timeoutMs = 20_000,
) {
  const cell = page.getByTestId(`watchlist-price-${ticker}`);
  const initial = await cell.textContent();
  await expect
    .poll(async () => cell.textContent(), {
      timeout: timeoutMs,
      message: `price for ${ticker} never changed from "${initial}"`,
    })
    .not.toBe(initial);
}

/**
 * Simulate a dropped connection by taking the browser context offline, then restoring it.
 * `EventSource` has no network-layer "abort" primitive Playwright can target reliably once
 * the stream is already open, so toggling offline mode is the reliable way to force a
 * disconnect + automatic reconnect.
 */
export async function simulateNetworkDrop(page: Page, durationMs = 3000) {
  await page.context().setOffline(true);
  await page.waitForTimeout(durationMs);
  await page.context().setOffline(false);
}
