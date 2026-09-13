import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TradeBar } from "@/components/TradeBar";
import { mockPrices } from "@/lib/fixtures";

const { postTradeMock } = vi.hoisted(() => ({ postTradeMock: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, postTrade: postTradeMock };
});

describe("TradeBar", () => {
  beforeEach(() => {
    postTradeMock.mockReset();
  });

  it("echoes the estimated cost before the trade is submitted", async () => {
    const user = userEvent.setup();
    render(<TradeBar selectedTicker={null} prices={mockPrices} onTraded={vi.fn()} />);
    await user.type(screen.getByTestId("trade-ticker"), "AAPL");
    await user.type(screen.getByTestId("trade-quantity"), "10");
    expect(screen.getByTestId("trade-estimate")).toHaveTextContent("$1,915.00");
  });

  it("shows 'Price unavailable' rather than a $0 estimate for an unpriced ticker", async () => {
    const user = userEvent.setup();
    render(<TradeBar selectedTicker={null} prices={{}} onTraded={vi.fn()} />);
    await user.type(screen.getByTestId("trade-ticker"), "ZZZZ");
    await user.type(screen.getByTestId("trade-quantity"), "5");
    expect(screen.getByTestId("trade-estimate")).toHaveTextContent("Price unavailable");
  });

  it("submits a buy and calls onTraded on success", async () => {
    postTradeMock.mockResolvedValue({
      trade: { ticker: "AAPL", side: "buy", quantity: 10, price: 191.5, total: 1915, executed_at: "now", cash_after: 8085 },
    });
    const onTraded = vi.fn();
    const user = userEvent.setup();
    render(<TradeBar selectedTicker="AAPL" prices={mockPrices} onTraded={onTraded} />);
    await user.type(screen.getByTestId("trade-quantity"), "10");
    await user.click(screen.getByTestId("trade-buy"));
    expect(postTradeMock).toHaveBeenCalledWith("AAPL", 10, "buy");
    expect(onTraded).toHaveBeenCalled();
  });

  it("renders the server's error message verbatim on a failed trade", async () => {
    const { ApiError } = await import("@/lib/api");
    postTradeMock.mockRejectedValue(new ApiError("INSUFFICIENT_CASH", "Need $1,900.00 but only $1,000.00 available."));
    const user = userEvent.setup();
    render(<TradeBar selectedTicker="AAPL" prices={mockPrices} onTraded={vi.fn()} />);
    await user.type(screen.getByTestId("trade-quantity"), "10");
    await user.click(screen.getByTestId("trade-buy"));
    expect(await screen.findByTestId("trade-error")).toHaveTextContent(
      "Need $1,900.00 but only $1,000.00 available.",
    );
  });
});
