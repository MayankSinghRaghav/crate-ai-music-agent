"use client";

import { useCallback, useEffect, useState } from "react";

/** Fisher–Yates sample of `n` items (non-mutating). */
function sample<T>(arr: T[], n: number): T[] {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, n);
}

/**
 * Shows a rotating subset of a theme's representative quotes. Renders a
 * deterministic slice on the server, then randomises after mount — so every
 * page refresh surfaces a fresh set (no hydration mismatch). A "shuffle"
 * control rotates them without a full reload.
 */
export function RotatingQuotes({
  quotes,
  show = 3,
}: {
  quotes: string[];
  show?: number;
}) {
  const [shown, setShown] = useState<string[]>(() => quotes.slice(0, show));
  const shuffle = useCallback(
    () => setShown(sample(quotes, show)),
    [quotes, show]
  );

  // randomise once on mount (i.e. on every page load)
  useEffect(() => {
    shuffle();
  }, [shuffle]);

  if (quotes.length === 0) return null;
  const canShuffle = quotes.length > show;

  return (
    <div className="mt-4 border-l-2 border-spotify-green/40 pl-3">
      <div className="mb-1 flex items-center gap-2">
        <p className="text-[11px] uppercase tracking-wide text-spotify-muted">
          Representative quotes
        </p>
        {canShuffle && (
          <button
            type="button"
            onClick={shuffle}
            aria-label="Show different quotes"
            className="rounded-full border border-spotify-border px-2 py-0.5 text-[10px] text-spotify-muted outline-none transition hover:text-white focus-visible:ring-2 focus-visible:ring-spotify-green"
          >
            ⟳ shuffle
          </button>
        )}
      </div>
      <ul className="space-y-1.5">
        {shown.map((q) => (
          <li key={q} className="animate-fade-up text-sm italic leading-snug text-white/85">
            &ldquo;{q}&rdquo;
          </li>
        ))}
      </ul>
    </div>
  );
}
