"use client";

import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { ChatTurn, Confidence } from "@/lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: number[];
  confidence?: Confidence;
  refused?: boolean;
  /** true when the assistant couldn't answer (API down / 503) — offers retry */
  error?: boolean;
}

const HISTORY_TURNS = 6; // matches the server-side cap

function makeId() {
  return Math.random().toString(36).slice(2);
}

/**
 * Conversation state for the Insights "ask" panel. The server is stateless, so
 * we send a capped slice of prior turns as grounding context each time. Answers
 * are grounded only in the discovery backlog; when the assistant is unavailable
 * we surface an honest error message (never a fabricated answer).
 */
export function useInsightsChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);

  const send = useCallback(
    async (raw: string) => {
      const question = raw.trim();
      if (!question || inFlight.current) return;
      inFlight.current = true;
      setLoading(true);

      // history = prior real (non-error) turns, capped
      const history: ChatTurn[] = messages
        .filter((m) => !m.error)
        .slice(-HISTORY_TURNS)
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [
        ...prev,
        { id: makeId(), role: "user", content: question },
      ]);

      try {
        const res = await api.askInsights(question, history);
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: "assistant",
            content: res.answer,
            citations: res.citations,
            confidence: res.confidence,
            refused: res.refused,
          },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: "assistant",
            content:
              "The insights assistant is unavailable right now. Please try again in a moment.",
            error: true,
          },
        ]);
      } finally {
        inFlight.current = false;
        setLoading(false);
      }
    },
    [messages]
  );

  const clear = useCallback(() => setMessages([]), []);

  return { messages, loading, send, clear };
}
