import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PositionsTable } from "@/components/PositionsTable";
import { computeLiveValuation } from "@/lib/portfolio";
import { mockPortfolio } from "@/lib/fixtures";

describe("PositionsTable", () => {
  it("renders a row per position with quantity and P&L testids", () => {
    const { positions } = computeLiveValuation(mockPortfolio, {});
    render(<PositionsTable positions={positions} onSelect={vi.fn()} />);
    expect(screen.getByTestId("positions-table")).toBeInTheDocument();
    expect(screen.getByTestId("position-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("position-qty-AAPL")).toHaveTextContent("10");
    expect(screen.getByTestId("position-pnl-AAPL")).toHaveTextContent("+$15.00");
  });

  it("renders unavailable, never $0, when a position has no price", () => {
    const portfolioWithGap = {
      ...mockPortfolio,
      positions: [{ ...mockPortfolio.positions[0]!, current_price: null }],
    };
    const { positions } = computeLiveValuation(portfolioWithGap, {});
    render(<PositionsTable positions={positions} onSelect={vi.fn()} />);
    expect(screen.getByText("unavailable")).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("shows an empty state with no positions", () => {
    render(<PositionsTable positions={[]} onSelect={vi.fn()} />);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });
});
