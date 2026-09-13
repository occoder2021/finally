import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WatchlistRow } from "@/components/WatchlistRow";
import type { PriceUpdate } from "@/lib/types";

function update(price: number): PriceUpdate {
  return { ticker: "AAPL", price, prev_price: price, day_open: 190, change_pct: 0.5, timestamp: 1, direction: "flat" };
}

describe("WatchlistRow price flash", () => {
  it("applies the up-flash class when the price rises between renders", () => {
    const { rerender } = render(
      <WatchlistRow ticker="AAPL" update={update(190)} sparkline={[]} selected={false} onSelect={vi.fn()} onRemove={vi.fn()} removing={false} />,
    );
    const priceCell = screen.getByTestId("watchlist-price-AAPL");
    expect(priceCell.parentElement).not.toHaveClass("animate-flash-up");

    rerender(
      <WatchlistRow ticker="AAPL" update={update(191)} sparkline={[]} selected={false} onSelect={vi.fn()} onRemove={vi.fn()} removing={false} />,
    );
    expect(priceCell.parentElement).toHaveClass("animate-flash-up");
  });

  it("applies the down-flash class when the price falls", () => {
    const { rerender } = render(
      <WatchlistRow ticker="AAPL" update={update(190)} sparkline={[]} selected={false} onSelect={vi.fn()} onRemove={vi.fn()} removing={false} />,
    );
    rerender(
      <WatchlistRow ticker="AAPL" update={update(188)} sparkline={[]} selected={false} onSelect={vi.fn()} onRemove={vi.fn()} removing={false} />,
    );
    expect(screen.getByTestId("watchlist-price-AAPL").parentElement).toHaveClass("animate-flash-down");
  });

  it("renders — for a ticker with no price yet, never $0", () => {
    render(<WatchlistRow ticker="GOOGL" update={undefined} sparkline={[]} selected={false} onSelect={vi.fn()} onRemove={vi.fn()} removing={false} />);
    expect(screen.getByTestId("watchlist-price-GOOGL")).toHaveTextContent("—");
  });

  it("labels the change figure as session change, never derived from the previous tick display", () => {
    render(<WatchlistRow ticker="AAPL" update={update(190)} sparkline={[]} selected={false} onSelect={vi.fn()} onRemove={vi.fn()} removing={false} />);
    const changeCell = screen.getByTestId("watchlist-change-AAPL");
    expect(changeCell.getAttribute("title")).toContain("Session");
  });
});
