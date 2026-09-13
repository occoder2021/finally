import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getPortfolio, getPriceHistory } from "@/lib/api";

describe("api error envelope", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws an ApiError with the server's code and message verbatim", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ error: { code: "INSUFFICIENT_CASH", message: "Need $1,900.00 but only $1,000.00 available." } }),
      }),
    );
    await expect(getPortfolio()).rejects.toMatchObject({
      code: "INSUFFICIENT_CASH",
      message: "Need $1,900.00 but only $1,000.00 available.",
    });
  });

  it("is an instance of ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ error: { code: "INVALID_TICKER", message: "'ZZZZ' is not a valid ticker symbol." } }),
      }),
    );
    try {
      await getPortfolio();
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
    }
  });

  it("treats a 404 from the price-history endpoint as 'no history yet', not an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    const res = await getPriceHistory("aapl");
    expect(res).toEqual({ ticker: "AAPL", points: [] });
  });
});
