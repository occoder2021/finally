"use client";

import { useEffect, useRef, useState } from "react";
import { formatCurrency, formatQuantity } from "@/lib/format";
import type { ChatAction, ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (text: string) => Promise<ChatAction[]>;
  onActionsExecuted: () => void;
}

export function ChatPanel({ messages, loading, onSend, onActionsExecuted }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, loading]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const actions = await onSend(text);
    if (actions.some((a) => a.status === "success")) onActionsExecuted();
  }

  return (
    <section data-testid="chat-panel" className="flex h-full flex-col">
      <h2 className="px-3 pb-2 pt-3 text-[13px] font-semibold text-ink-primary">AI chat</h2>

      <div ref={listRef} className="scroll-thin flex-1 space-y-2.5 overflow-y-auto px-3">
        {messages.length === 0 && !loading && (
          <p className="pt-4 text-[12px] text-ink-muted">
            Ask FinAlly about your portfolio, or tell it to make a trade.
          </p>
        )}
        {messages.map((msg, i) => (
          <ChatBubble key={i} index={i} message={msg} />
        ))}
        {loading && (
          <div data-testid="chat-loading" className="flex items-center gap-1.5 text-[12px] text-ink-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            FinAlly is thinking…
          </div>
        )}
      </div>

      <form onSubmit={handleSend} className="flex gap-1.5 border-t border-line p-3">
        <input
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your portfolio…"
          disabled={loading}
          className="w-full rounded border border-line bg-base-raised px-2.5 py-1.5 text-[12.5px] text-ink-primary placeholder:text-ink-muted focus:border-blue focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          data-testid="chat-send"
          disabled={loading || !input.trim()}
          className="shrink-0 rounded bg-purple px-3 py-1.5 text-[12.5px] font-medium text-white transition-colors hover:bg-purple-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </section>
  );
}

function ChatBubble({ index, message }: { index: number; message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div data-testid={`chat-message-${index}`} data-role={message.role} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={`max-w-[92%] rounded-lg px-2.5 py-1.5 text-[12.5px] leading-snug ${
          isUser ? "bg-blue-dim text-ink-primary" : "bg-base-raised text-ink-primary"
        }`}
      >
        {message.content}
      </div>
      {message.actions && message.actions.length > 0 && (
        <div className="mt-1 flex max-w-[92%] flex-col gap-1">
          {message.actions.map((action, i) => (
            <ActionLine key={i} index={i} action={action} />
          ))}
        </div>
      )}
    </div>
  );
}

function ActionLine({ index, action }: { index: number; action: ChatAction }) {
  const ok = action.status === "success";
  const summary =
    action.type === "trade"
      ? `${action.side === "buy" ? "Buy" : "Sell"} ${formatQuantity(action.quantity)} ${action.ticker}${
          ok && action.price !== undefined ? ` @ ${formatCurrency(action.price)}` : ""
        }`
      : `${action.action === "add" ? "Add" : "Remove"} ${action.ticker}`;

  return (
    <div
      data-testid={`chat-action-${index}`}
      data-status={action.status}
      className={`flex items-start gap-1.5 rounded border px-2 py-1 text-[11.5px] ${
        ok ? "border-good/30 bg-good-dim text-good-text" : "border-critical/30 bg-critical-dim text-critical-text"
      }`}
    >
      <span aria-hidden="true">{ok ? "✓" : "✕"}</span>
      <span>
        <span className="font-medium">{summary}</span>
        <span className="block text-ink-secondary">{action.detail}</span>
      </span>
    </div>
  );
}
