"use client";

import type { Confidence } from "@/lib/types";
import type { ChatMessage as Message } from "@/hooks/useInsightsChat";

import { CitationChip } from "./CitationChip";

const CONFIDENCE_STYLE: Record<Confidence, string> = {
  high: "bg-spotify-green/15 text-spotify-green",
  medium: "bg-amber-500/15 text-amber-300",
  low: "bg-spotify-elevated text-spotify-muted",
};

export function ChatMessage({
  message,
  onCite,
}: {
  message: Message;
  onCite: (rank: number) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="animate-pop-in max-w-[85%] rounded-2xl rounded-br-sm bg-spotify-green px-3.5 py-2 text-sm font-medium text-black">
          {message.content}
        </div>
      </div>
    );
  }

  // assistant
  const { content, citations, confidence, refused, error } = message;
  return (
    <div className="flex justify-start">
      <div
        className={`animate-pop-in max-w-[92%] rounded-2xl rounded-bl-sm border px-3.5 py-2.5 ${
          error
            ? "border-red-500/30 bg-red-500/10"
            : "border-spotify-border bg-spotify-elevated"
        }`}
      >
        <p
          className={`whitespace-pre-wrap text-sm leading-relaxed ${
            error ? "text-red-200" : "text-white/90"
          }`}
        >
          {content}
        </p>

        {!error && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {confidence && !refused && (
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${CONFIDENCE_STYLE[confidence]}`}
              >
                {confidence} confidence
              </span>
            )}
            {citations && citations.length > 0 && (
              <>
                <span className="text-[11px] text-spotify-muted">Sources:</span>
                {citations.map((rank) => (
                  <CitationChip key={rank} rank={rank} onCite={onCite} />
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
