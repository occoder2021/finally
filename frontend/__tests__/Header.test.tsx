import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Header } from "@/components/Header";

describe("Header", () => {
  it("maps connection state to the dot's data-state attribute", () => {
    const { rerender } = render(
      <Header totalValue={10000} startingCash={10000} cashBalance={10000} connectionState="connected" hasUnavailable={false} />,
    );
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "connected");

    rerender(<Header totalValue={10000} startingCash={10000} cashBalance={10000} connectionState="connecting" hasUnavailable={false} />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "connecting");

    rerender(<Header totalValue={10000} startingCash={10000} cashBalance={10000} connectionState="disconnected" hasUnavailable={false} />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "disconnected");
  });

  it("shows total value, cash and return figures", () => {
    render(<Header totalValue={10015} startingCash={10000} cashBalance={8100} connectionState="connected" hasUnavailable={false} />);
    expect(screen.getByTestId("total-value")).toHaveTextContent("$10,015.00");
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("$8,100.00");
    expect(screen.getByTestId("total-return")).toHaveTextContent("+$15.00");
  });
});
