import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Watchlist } from "@/components/Watchlist";
import { ApiError } from "@/lib/api";
import { mockPrices } from "@/lib/fixtures";

describe("Watchlist", () => {
  it("renders a row per ticker with testids from the contract", () => {
    render(
      <Watchlist
        tickers={["AAPL", "GOOGL"]}
        prices={mockPrices}
        sparklines={{}}
        selectedTicker={null}
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByTestId("watchlist")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-GOOGL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("$191.50");
  });

  it("selects a ticker when its row is clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <Watchlist tickers={["AAPL"]} prices={mockPrices} sparklines={{}} selectedTicker={null} onSelect={onSelect} onAdd={vi.fn()} onRemove={vi.fn()} />,
    );
    await user.click(screen.getByTestId("watchlist-row-AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("adds a ticker through the add form", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <Watchlist tickers={["AAPL"]} prices={mockPrices} sparklines={{}} selectedTicker={null} onSelect={vi.fn()} onAdd={onAdd} onRemove={vi.fn()} />,
    );
    await user.type(screen.getByTestId("watchlist-add-input"), "pypl");
    await user.click(screen.getByTestId("watchlist-add-submit"));
    expect(onAdd).toHaveBeenCalledWith("PYPL");
  });

  it("shows the server's error message verbatim in watchlist-error when adding fails", async () => {
    const onAdd = vi.fn().mockRejectedValue(new ApiError("WATCHLIST_FULL", "Watchlist is full (25 tickers max)."));
    const user = userEvent.setup();
    render(
      <Watchlist tickers={["AAPL"]} prices={mockPrices} sparklines={{}} selectedTicker={null} onSelect={vi.fn()} onAdd={onAdd} onRemove={vi.fn()} />,
    );
    await user.type(screen.getByTestId("watchlist-add-input"), "ZZZZ");
    await user.click(screen.getByTestId("watchlist-add-submit"));
    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent("Watchlist is full (25 tickers max).");
  });

  it("clears watchlist-error on the next successful add", async () => {
    const onAdd = vi.fn().mockRejectedValueOnce(new ApiError("DUPLICATE_TICKER", "AAPL is already on your watchlist.")).mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(
      <Watchlist tickers={["AAPL"]} prices={mockPrices} sparklines={{}} selectedTicker={null} onSelect={vi.fn()} onAdd={onAdd} onRemove={vi.fn()} />,
    );
    await user.type(screen.getByTestId("watchlist-add-input"), "AAPL");
    await user.click(screen.getByTestId("watchlist-add-submit"));
    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent("AAPL is already on your watchlist.");

    await user.type(screen.getByTestId("watchlist-add-input"), "PYPL");
    await user.click(screen.getByTestId("watchlist-add-submit"));
    expect(screen.queryByTestId("watchlist-error")).not.toBeInTheDocument();
  });

  it("removes a ticker when its remove button is clicked, without selecting the row", async () => {
    const onRemove = vi.fn().mockResolvedValue(undefined);
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <Watchlist tickers={["AAPL"]} prices={mockPrices} sparklines={{}} selectedTicker={null} onSelect={onSelect} onAdd={vi.fn()} onRemove={onRemove} />,
    );
    await user.click(screen.getByTestId("watchlist-remove-AAPL"));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
    expect(onSelect).not.toHaveBeenCalled();
  });
});
