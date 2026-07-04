"use client";

// Grounded in what the dashboard can actually answer (sentiment, segments,
// unmet needs, ranking) so the first click always yields a cited answer.
const SUGGESTIONS = [
  "What's the #1 opportunity and why?",
  "Which themes have negative sentiment?",
  "What do power users struggle with?",
  "Summarize the top 3 unmet needs.",
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
