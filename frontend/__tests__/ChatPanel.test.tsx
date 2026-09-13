import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/ChatPanel";
import { mockChatMessages } from "@/lib/fixtures";

describe("ChatPanel", () => {
  it("renders history messages with role-tagged testids", () => {
    render(<ChatPanel messages={mockChatMessages} loading={false} onSend={vi.fn()} onActionsExecuted={vi.fn()} />);
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
    expect(screen.getByTestId("chat-message-0")).toHaveAttribute("data-role", "user");
    expect(screen.getByTestId("chat-message-1")).toHaveAttribute("data-role", "assistant");
  });

  it("renders each action's actual outcome, never the model's prose, as evidence of execution", () => {
    render(<ChatPanel messages={mockChatMessages} loading={false} onSend={vi.fn()} onActionsExecuted={vi.fn()} />);
    const action = screen.getByTestId("chat-action-0");
    expect(action).toHaveAttribute("data-status", "success");
    expect(action).toHaveTextContent("Bought 5 NVDA at $480.12");
  });

  it("shows a failed action distinctly from a successful one", () => {
    const messages = [
      {
        role: "assistant" as const,
        content: "Tried to buy TSLA.",
        actions: [
          {
            type: "trade" as const,
            status: "failed" as const,
            ticker: "TSLA",
            side: "buy" as const,
            quantity: 100,
            detail: "Need $24,000.00 but only $1,200.00 available.",
          },
        ],
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    render(<ChatPanel messages={messages} loading={false} onSend={vi.fn()} onActionsExecuted={vi.fn()} />);
    const action = screen.getByTestId("chat-action-0");
    expect(action).toHaveAttribute("data-status", "failed");
    expect(action).toHaveTextContent("Need $24,000.00 but only $1,200.00 available.");
  });

  it("shows the loading indicator while waiting for a response", () => {
    render(<ChatPanel messages={[]} loading={true} onSend={vi.fn()} onActionsExecuted={vi.fn()} />);
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
  });

  it("sends a message and clears the input", async () => {
    const onSend = vi.fn().mockResolvedValue([]);
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} loading={false} onSend={onSend} onActionsExecuted={vi.fn()} />);
    await user.type(screen.getByTestId("chat-input"), "Buy 5 NVDA");
    await user.click(screen.getByTestId("chat-send"));
    expect(onSend).toHaveBeenCalledWith("Buy 5 NVDA");
    expect(screen.getByTestId("chat-input")).toHaveValue("");
  });

  it("triggers a portfolio refresh only when an action actually succeeded", async () => {
    const onActionsExecuted = vi.fn();
    const onSend = vi.fn().mockResolvedValue([
      { type: "trade", status: "success", ticker: "NVDA", side: "buy", quantity: 1, detail: "ok" },
    ]);
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} loading={false} onSend={onSend} onActionsExecuted={onActionsExecuted} />);
    await user.type(screen.getByTestId("chat-input"), "Buy 1 NVDA");
    await user.click(screen.getByTestId("chat-send"));
    expect(onActionsExecuted).toHaveBeenCalled();
  });
});
