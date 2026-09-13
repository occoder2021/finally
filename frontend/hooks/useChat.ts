"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getChatHistory, postChat } from "@/lib/api";
import type { ChatAction, ChatMessage } from "@/lib/types";

export interface ChatState {
  messages: ChatMessage[];
  loading: boolean;
  historyError: string | null;
  send: (text: string) => Promise<ChatAction[]>;
}

/**
 * Loads `/api/chat/history` once on mount so a page refresh restores the
 * visible conversation (TEAM_CONTRACT §7 / PLAN.md G2), then appends locally
 * as the user sends messages. `send` returns the executed actions so the
 * caller (page.tsx) can refetch portfolio/watchlist after AI-initiated trades
 * or watchlist changes — the same refresh rule manual trades follow.
 */
export function useChat(): ChatState {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getChatHistory();
        if (!cancelled) setMessages(data.messages);
      } catch (err) {
        if (!cancelled) {
          setHistoryError(err instanceof ApiError ? err.message : "Could not load chat history.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const send = useCallback(async (text: string): Promise<ChatAction[]> => {
    const trimmed = text.trim();
    if (!trimmed) return [];

    const userMessage: ChatMessage = {
      role: "user",
      content: trimmed,
      actions: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const res = await postChat(trimmed);
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: res.message,
        actions: res.actions,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      return res.actions;
    } catch (err) {
      // Chat unavailable (no API key) or a malformed/errored LLM response:
      // report it as the assistant's turn, in plain language, never as a
      // fabricated successful reply (PLAN.md §5 / §14.3).
      const message = err instanceof ApiError ? err.message : "Something went wrong reaching the AI assistant.";
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: message,
        actions: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  return { messages, loading, historyError, send };
}
