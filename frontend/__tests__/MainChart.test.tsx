import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MainChart } from "@/components/MainChart";

vi.mock("lightweight-charts", () => {
  const series = { setData: vi.fn(), update: vi.fn() };
  const chart = {
    addLineSeries: vi.fn(() => series),
    remove: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
  };
  return {
    createChart: vi.fn(() => chart),
    ColorType: { Solid: "solid" },
  };
});

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, getPriceHistory: vi.fn().mockResolvedValue({ ticker: "AAPL", points: [] }) };
});

describe("MainChart", () => {
  it("prompts for a selection when no ticker is chosen", () => {
    render(<MainChart ticker={null} latestUpdate={undefined} />);
    expect(screen.getByTestId("main-chart")).toBeInTheDocument();
    expect(screen.getByText(/pick a ticker/i)).toBeInTheDocument();
  });

  it("shows the selected ticker's symbol and live price", () => {
    render(
      <MainChart
        ticker="AAPL"
        latestUpdate={{ ticker: "AAPL", price: 191.5, prev_price: 190, day_open: 190, change_pct: 0.79, timestamp: 1, direction: "up" }}
      />,
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("$191.50")).toBeInTheDocument();
  });
});
