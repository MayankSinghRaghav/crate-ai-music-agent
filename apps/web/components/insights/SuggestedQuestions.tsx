"use client";

// Plain-language questions the dashboard can actually answer from its themes,
// so the first click always yields a cited answer.
const SUGGESTIONS = [
  "What's the biggest thing users want?",
  "What are people most frustrated about?",
  "What do power users struggle with?",
  "What should we build first?",
];

export function SuggestedQuestions({
  onPick,
  disabled,
}: {
  onPick: (question: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {SUGGESTIONS.map((q) => (
        <button
          key={q}
          type="button"
          disabled={disabled}
          onClick={() => onPick(q)}
          className="rounded-full border border-spotify-border bg-spotify-surface px-3 py-1.5 text-left text-xs text-spotify-subtle outline-none transition hover:border-spotify-muted hover:text-white focus-visible:ring-2 focus-visible:ring-spotify-green disabled:cursor-not-allowed disabled:opacity-50 active:scale-95"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
