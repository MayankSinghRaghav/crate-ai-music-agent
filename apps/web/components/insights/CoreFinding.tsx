"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

/**
 * The synthesised "core finding" banner at the top of the Insights page.
 * Renders a deterministic fallback immediately (works even if the API is down),
 * then upgrades to the AI-written summary once the backend responds.
 */
export function CoreFinding({
  fallback,
  reviewsAnalysed,
}: {
  fallback: string;
  reviewsAnalysed: number;
}) {
  const [summary, setSummary] = useState(fallback);
  const [analysed, setAnalysed] = useState(reviewsAnalysed);
  const [ai, setAi] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .insightsSummary()
      .then((s) => {
        if (!alive) return;
        setSummary(s.summary);
        setAnalysed(s.reviews_analysed || reviewsAnalysed);
        setAi(s.generated);
      })
      .catch(() => {
        /* keep the deterministic fallback */
      });
    return () => {
      alive = false;
    };
  }, [reviewsAnalysed]);

  return (
    <div className="rounded-2xl border border-spotify-green/30 bg-gradient-to-b from-spotify-green/10 to-transparent p-5 sm:p-6">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-spotify-green">
        Core finding · {analysed.toLocaleString()} reviews analysed
        {ai && <span className="ml-1 text-spotify-muted">· AI-written</span>}
      </p>
      <p className="mt-2 text-lg font-semibold leading-snug text-white sm:text-xl">
        {summary}
      </p>
    </div>
  );
}
