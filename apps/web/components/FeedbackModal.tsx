"use client";

import { useState } from "react";
import type { DigItem } from "@/lib/types";

const QUICK_REASONS = [
  "Not my vibe",
  "Too far from my taste",
  "Heard it already",
  "Wrong mood",
  "Don't like this artist",
];

export function FeedbackModal({
  item,
  onClose,
  onSubmit,
}: {
  item: DigItem;
  onClose: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="animate-pop-in w-full max-w-md rounded-2xl border border-spotify-border bg-spotify-elevated p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">Tell me why</h3>
        <p className="mt-1 text-sm text-spotify-subtle">
          Skipping <span className="text-white">{item.track.title}</span> by{" "}
          <span className="text-white">{item.track.artist}</span>. I'll keep this
          artist out of your future digs.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {QUICK_REASONS.map((r) => (
            <button
              key={r}
              onClick={() => setReason(r)}
              className={`rounded-full border px-3 py-1.5 text-sm transition ${
                reason === r
                  ? "border-spotify-green bg-spotify-green/10 text-spotify-green"
                  : "border-spotify-border text-spotify-subtle hover:text-white"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="…or say it in your own words"
          rows={2}
          className="mt-3 w-full resize-none rounded-lg border border-spotify-border bg-spotify-surface px-3 py-2 text-sm text-white placeholder:text-spotify-muted focus:border-spotify-green focus:outline-none"
        />

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-full border border-spotify-border px-4 py-2 text-sm text-spotify-subtle transition hover:text-white"
          >
            Cancel
          </button>
          <button
            onClick={() => onSubmit(reason.trim())}
            className="rounded-full bg-spotify-green px-4 py-2 text-sm font-semibold text-black transition hover:bg-spotify-greenDark"
          >
            Submit &amp; adapt
          </button>
        </div>
      </div>
    </div>
  );
}
