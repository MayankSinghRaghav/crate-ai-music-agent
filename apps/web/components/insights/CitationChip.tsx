"use client";

/** A clickable citation that jumps to (and flashes) the referenced theme card. */
export function CitationChip({
  rank,
  onCite,
}: {
  rank: number;
  onCite: (rank: number) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onCite(rank)}
      aria-label={`Jump to theme ${rank}`}
      className="rounded-full border border-spotify-green/40 bg-spotify-green/10 px-2 py-0.5 text-[11px] font-medium text-spotify-green outline-none transition hover:bg-spotify-green/20 focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-spotify-black"
    >
      #{rank}
    </button>
  );
}
