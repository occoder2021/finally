import { test, expect } from "@playwright/test";
import { SCRATCH_TICKERS, scratchTickerCleanup } from "../fixtures/reset";

/**
 * Requires `LLM_MOCK=true` (forced via playwright.config.ts webServer.env). Per
 * TEAM_CONTRACT.md §7, mock mode is deterministic but still exercises the real execution
 * path: a message containing "buy N TICKER" / "sell N TICKER" produces that trade action
 * through the same `execute_trade` path as the manual trade bar.
 */

const TICKER = SCRATCH_TICKERS.chat;

// Locate message/action bubbles by testid prefix rather than a hardcoded numeric index —
// the `{index}` in `chat-message-{index}` / `chat-action-{index}` (TEAM_CONTRACT.md §8) is
// not guaranteed to start at 0 once chat history has accumulated across specs sharing one DB.
const messageLocator = (page: import("@playwright/test").Page) =>
  page.locator('[data-testid^="chat-message-"]');
const actionLocator = (page: import("@playwright/test").Page) =>
  page.locator('[data-testid^="chat-action-"]');

test.describe("AI chat", () => {
  test.afterEach(async ({ request }) => {
    await scratchTickerCleanup(request, TICKER);
  });

  test("sending a message renders the reply and a successful trade action", async ({ page }) => {
    await page.goto("/");

    const before = await messageLocator(page).count();

    await page.getByTestId("chat-input").fill(`buy 1 ${TICKER}`);
    await page.getByTestId("chat-send").click();

    // Two new bubbles: the user's message and the assistant's reply.
    await expect
      .poll(async () => messageLocator(page).count(), {
        timeout: 15_000,
        message: "chat did not add a new user+assistant message pair",
      })
      .toBeGreaterThanOrEqual(before + 2);

    const lastAssistant = messageLocator(page).last();
    await expect(lastAssistant).toHaveAttribute("data-role", "assistant");

    const action = actionLocator(page).last();
    await expect(action).toBeVisible();
    await expect(action).toHaveAttribute("data-status", "success");

    // The backend is the source of truth for whether the trade happened, not the model's
    // prose — confirm the position actually exists.
    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
  });

  test("a trade that fails validation renders as failed, not as the model's claimed success", async ({
    page,
  }) => {
    await page.goto("/");

    // An absurd quantity guarantees INSUFFICIENT_CASH regardless of current cash balance.
    await page.getByTestId("chat-input").fill(`buy 999999999 ${TICKER}`);
    await page.getByTestId("chat-send").click();

    const action = actionLocator(page).last();
    await expect(action).toBeVisible({ timeout: 15_000 });
    await expect(action).toHaveAttribute("data-status", "failed");

    await expect(page.getByTestId(`position-row-${TICKER}`)).toHaveCount(0);
  });

  test("chat history persists across a page reload", async ({ page }) => {
    await page.goto("/");
    const marker = `analysis check ${Date.now()}`;
    await page.getByTestId("chat-input").fill(marker);
    await page.getByTestId("chat-send").click();

    await expect
      .poll(async () => messageLocator(page).count(), { timeout: 15_000 })
      .toBeGreaterThan(0);

    await page.reload();

    await expect(page.getByTestId("chat-panel")).toBeVisible();
    await expect(messageLocator(page).filter({ hasText: marker })).toBeVisible();
  });
});
