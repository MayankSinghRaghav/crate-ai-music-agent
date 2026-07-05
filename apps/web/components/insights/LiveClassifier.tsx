"use client";

import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Classification } from "@/lib/types";

const SAMPLES = [
  "I keep hearing the same 30 songs on shuffle even though I have 500 liked songs.",
  "The algorithm never understands my mood. When I'm studying it plays hype music.",
  "As a free user I can't skip or choose songs. Discovery is impossible.",
  "Discover Weekly is just my most played songs recycled. Nothing new ever.",
];

const INTENSITY_STYLE: Record<Classification["intensity"], string> = {
  high: "bg-red-500/15 text-red-300",
  medium: "bg-amber-500/15 text-amber-300",
  low: "bg-spotify-elevated text-spotify-muted",
};

const MAX_LEN = 1000;

export function LiveClassifier() {
  const [review, setReview] = useState("");
  const [result, setResult] = useState<Classification | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const inFlight = useRef(false);

  const classify = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t || inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(false);
    try {
      setResult(await api.classify(t));
    } catch {
      setError(true);
      setResult(null);
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, []);

  return (
    <section
      aria-label="Live review classifier"
      className="rounded-2xl border border-spotify-border bg-spotify-card p-4 sm:p-5"
    >
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <span aria-hidden>🔍</span> Classify any review
      </h2>
      <p className="mt-0.5 text-xs text-spotify-muted">
        Paste a Spotify review — the AI tags the frustration type, what the user
        is trying to do, their segment, and how strongly they feel it.
      </p>

      <div className="mt-4 flex items-end gap-2">
        <textarea
          value={review}
          onChange={(e) => setReview(e.target.value.slice(0, MAX_LEN))}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") classify(review);
          }}
          rows={2}
          aria-label="Review text to classify"
          placeholder="Paste a review to classify…"
          className="max-h-40 flex-1 resize-none rounded-xl border border-spotify-border bg-spotify-surface px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-spotify-muted focus:border-spotify-green focus-visible:ring-1 focus-visible:ring-spotify-green"
        />
        <button
          type="button"
          onClick={() => classify(review)}
          disabled={!review.trim() || loading}
          className="shrink-0 rounded-xl bg-spotify-green px-4 py-2.5 text-sm font-semibold text-black outline-none transition hover:bg-spotify-greenDark focus-visible:ring-2 focus-visible:ring-spotify-green disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Classifying…" : "Classify"}
        </button>
      </div>
      <p className="mt-1.5 text-[10px] text-spotify-muted">Press ⌘/Ctrl + Enter to classify</p>

      {error && (
        <p className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          Couldn&apos;t reach the classifier. Please try again.
        </p>
      )}

      {result && !error && (
        <div className="animate-pop-in mt-3 rounded-xl border border-spotify-green/40 bg-spotify-elevated p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-red-500/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-red-300">
              {result.frustration_type}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${INTENSITY_STYLE[result.intensity]}`}
            >
              {result.intensity} intensity
            </span>
          </div>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex gap-2">
              <dt className="shrink-0 text-spotify-muted">🎯 Job-to-be-done:</dt>
              <dd className="text-white/90">{result.job_to_be_done}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="shrink-0 text-spotify-muted">👤 Segment:</dt>
              <dd className="text-white/90">{result.segment}</dd>
            </div>
          </dl>
        </div>
      )}

      <p className="mt-4 text-[11px] uppercase tracking-wide text-spotify-muted">
        Try one
      </p>
      <div className="mt-2 space-y-1.5">
        {SAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            disabled={loading}
            onClick={() => {
              setReview(s);
              classify(s);
            }}
            className="block w-full rounded-lg border border-spotify-border bg-spotify-surface px-3 py-2 text-left text-xs text-spotify-subtle outline-none transition hover:border-spotify-muted hover:text-white focus-visible:ring-2 focus-visible:ring-spotify-green disabled:opacity-50"
          >
            &ldquo;{s}&rdquo;
          </button>
        ))}
      </div>
    </section>
  );
}
