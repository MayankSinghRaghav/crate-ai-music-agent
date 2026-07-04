"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useInsightsChat } from "@/hooks/useInsightsChat";

import { ChatMessage } from "./ChatMessage";
import { SuggestedQuestions } from "./SuggestedQuestions";

const MAX_LEN = 500;

export function InsightsChat({ themeCount }: { themeCount: number }) {
  const { messages, loading, send, clear } = useInsightsChat();
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  // keep the newest message / loading indicator in view
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const submit = useCallback(
    (q: string) => {
      if (!q.trim() || loading) return;
      send(q);
      setInput("");
    },
    [send, loading]
  );

  // Jump to and flash the referenced theme card on the page.
  const handleCite = useCallback((rank: number) => {
    const el = document.getElementById(`theme-${rank}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("theme-flash");
    void el.offsetWidth; // restart the animation
    el.classList.add("theme-flash");
  }, []);

  const canSend = input.trim().length > 0 && !loading;
  const hasMessages = messages.length > 0;

  return (
    <section
      aria-label="Ask the insights"
      className="rounded-2xl border border-spotify-border bg-spotify-card p-4 sm:p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <span aria-hidden>✨</span> Ask the Insights
          </h2>
          <p className="mt-0.5 text-xs text-spotify-muted">
            Answers are grounded only in the {themeCount} discovery themes below —
            with citations you can click.
          </p>
        </div>
        {hasMessages && (
          <button
            type="button"
            onClick={clear}
            className="shrink-0 rounded-full border border-spotify-border px-2.5 py-1 text-[11px] text-spotify-subtle outline-none transition hover:text-white focus-visible:ring-2 focus-visible:ring-spotify-green"
          >
            Clear
          </button>
        )}
      </div>

      {/* conversation / empty state */}
      <div
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-busy={loading}
        className="mt-4 max-h-[22rem] space-y-3 overflow-y-auto scroll-smooth"
      >
        {!hasMessages && !loading ? (
          <div className="rounded-xl border border-dashed border-spotify-border p-4">
            <p className="text-sm text-spotify-subtle">
              Ask about sentiment, segments, unmet needs, or which theme is the
              biggest opportunity. Try one:
            </p>
            <div className="mt-3">
              <SuggestedQuestions onPick={submit} disabled={loading} />
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <ChatMessage key={m.id} message={m} onCite={handleCite} />
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm border border-spotify-border bg-spotify-elevated px-3.5 py-2.5">
              <span className="h-2 w-2 animate-pulse rounded-full bg-spotify-green" />
              <span className="text-sm text-spotify-muted">Reading the backlog…</span>
            </div>
          </div>
        )}
      </div>

      {/* input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="mt-4"
      >
        <div className="flex items-end gap-2">
          <div className="relative flex-1">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value.slice(0, MAX_LEN))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(input);
                }
              }}
              rows={1}
              aria-label="Ask a question about the discovery insights"
              placeholder="Ask a question about these insights…"
              className="max-h-32 w-full resize-none rounded-xl border border-spotify-border bg-spotify-surface px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-spotify-muted focus:border-spotify-green focus-visible:ring-1 focus-visible:ring-spotify-green"
            />
            {input.length > MAX_LEN - 100 && (
              <span className="pointer-events-none absolute bottom-1.5 right-2 text-[10px] text-spotify-muted">
                {input.length}/{MAX_LEN}
              </span>
            )}
          </div>
          <button
            type="submit"
            disabled={!canSend}
            className="shrink-0 rounded-xl bg-spotify-green px-4 py-2.5 text-sm font-semibold text-black outline-none transition hover:bg-spotify-greenDark focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-spotify-black disabled:cursor-not-allowed disabled:opacity-40"
          >
            Ask
          </button>
        </div>
        <p className="mt-1.5 text-[10px] text-spotify-muted">
          Press Enter to send · Shift+Enter for a new line
        </p>
      </form>
    </section>
  );
}
