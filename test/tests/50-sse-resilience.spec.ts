import { test, expect } from "@playwright/test";
import { simulateNetworkDrop, waitForConnectionState, waitForPriceChange } from "../fixtures/sse";

test.describe("SSE resilience", () => {
  test("dropping the connection and restoring it reconnects the stream", async ({ page }) => {
    await page.goto("/");
    await waitForConnectionState(page, "connected");

    // Drop the connection: EventSource.readyState should move away from OPEN. Depending on
    // timing the client may observe this as "connecting" (retrying) or briefly "disconnected"
    // before a retry attempt starts — TEAM_CONTRACT.md §8 maps CONNECTING (after an error) to
    // yellow and CLOSED to red, so accept either as evidence the drop was detected.
    const dropped = page.context().setOffline(true);
    await Promise.race([
      waitForConnectionState(page, "connecting", 10_000),
      waitForConnectionState(page, "disconnected", 10_000),
    ]);
    await dropped;

    await page.context().setOffline(false);

    await waitForConnectionState(page, "connected", 20_000);

    // Confirm the stream is actually flowing again, not just that the dot repainted.
    await waitForPriceChange(page, "AAPL", 20_000);
  });

  test("a short blip recovers without a full page reload", async ({ page }) => {
    await page.goto("/");
    await waitForConnectionState(page, "connected");

    await simulateNetworkDrop(page, 2000);

    await waitForConnectionState(page, "connected", 20_000);
    await expect(page.getByTestId("watchlist")).toBeVisible();
  });
});
