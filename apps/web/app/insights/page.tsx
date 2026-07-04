// Discovery Insights dashboard — renders the ranked opportunity backlog produced
// by ingest/ (7 public review/social sources → dedupe → cluster → LLM tag).
// Server component: reads the JSON snapshot at build time — no runtime API.
// ponytail: static import of the daily-refreshed snapshot; upgrade to fetch()
// off a cache API only if the snapshot ever gets too big to ship in the bundle.
import Link from "next/link";

import { InsightsChat } from "@/components/insights/InsightsChat";
import { Logo } from "@/components/Logo";
import opportunities from "@/lib/opportunities.json";

type Sentiment = "negative" | "mixed" | "positive";

interface Theme {
  rank: number;
  topic: string;
  size: number;
  share: number;
  sentiment: Sentiment;
  segment: string;
  unmet_need: string;
  research_question?: string;
  keywords: string[];
  example_quotes: string[];
  opportunity_score: number;
}

const SOURCES = [
  { name: "Reddit", desc: "r/spotify · r/truespotify — official PRAW API" },
  { name: "App Store", desc: "iOS customer reviews — Apple RSS feed" },
  { name: "Google Play", desc: "Android reviews — google-play-scraper" },
  { name: "X / Twitter", desc: "public tweets — X API v2" },
  { name: "YouTube", desc: "comments on relevant videos — Data API v3" },
  { name: "Product Hunt", desc: "reviews via GraphQL API" },
  { name: "Spotify Community", desc: "official support forum — Khoros API" },
];

const SENTIMENT_STYLE: Record<Sentiment, string> = {
  negative: "bg-red-500/15 text-red-300 border-red-500/30",
  mixed: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  positive: "bg-spotify-green/15 text-spotify-green border-spotify-green/30",
};

const themes = opportunities as Theme[];
const totalDocs = themes.reduce((a, t) => a + t.size, 0);
const topSentiment = themes.reduce(
  (a, t) => ({ ...a, [t.sentiment]: (a[t.sentiment] || 0) + 1 }),
  {} as Record<string, number>
);

export const metadata = {
  title: "Discovery Insights — Crate",
  description: "Ranked opportunity backlog from 7 public review sources.",
};

export default function InsightsPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <header className="flex items-center justify-between">
        <Logo />
        <Link
          href="/"
          className="rounded-full border border-spotify-border bg-spotify-surface px-3 py-1 text-xs text-spotify-subtle transition hover:text-white"
        >
          ← Today&apos;s Dig
        </Link>
      </header>

      {/* hero */}
      <section className="mt-8">
        <p className="text-xs uppercase tracking-wide text-spotify-muted">
          AI Review Discovery Engine
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">
          Why users struggle to discover new music
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-spotify-subtle sm:text-base">
          A pipeline that mines public conversation across 7 sources, dedupes
          across channels, clusters into themes, and tags each with{" "}
          <span className="text-white">topic · sentiment · unmet-need · segment</span>{" "}
          — producing the ranked backlog of opportunities below. #1 theme is
          exactly Crate&apos;s founding thesis.
        </p>

        {/* headline stats */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Documents mined" value={totalDocs.toLocaleString()} />
          <Stat label="Sources" value="7" />
          <Stat label="Themes surfaced" value={String(themes.length)} />
          <Stat
            label="Negative signal"
            value={`${topSentiment.negative || 0} of ${themes.length}`}
          />
        </div>
      </section>

      {/* ask the insights — grounded AI chat over the backlog below */}
      <section className="mt-10">
        <InsightsChat />
      </section>

      {/* sources */}
      <section className="mt-10">
        <h2 className="text-xs uppercase tracking-wide text-spotify-muted">
          Sources
        </h2>
        <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCES.map((s) => (
            <li
              key={s.name}
              className="rounded-lg border border-spotify-border bg-spotify-surface px-3 py-2"
            >
              <p className="text-sm font-medium">{s.name}</p>
              <p className="text-[11px] text-spotify-muted">{s.desc}</p>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-spotify-muted">
          Refreshed daily by GitHub Actions (09:15 IST). Each source degrades
          gracefully to bundled offline fixtures when credentials are absent.
        </p>
      </section>

      {/* ranked backlog */}
      <section className="mt-10">
        <h2 className="text-xs uppercase tracking-wide text-spotify-muted">
          Ranked opportunity backlog
        </h2>
        <p className="mt-1 text-sm text-spotify-subtle">
          Sorted by <span className="text-white">opportunity score</span> (theme
          size × sentiment weight — bigger, angrier themes rank higher).
        </p>

        <ol className="mt-4 space-y-4">
          {themes.map((t) => (
            <li
              key={t.rank}
              id={`theme-${t.rank}`}
              className="scroll-mt-20 rounded-xl border border-spotify-border bg-spotify-card p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-spotify-green text-sm font-bold text-black">
                    {t.rank}
                  </span>
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold leading-tight">
                      {t.topic}
                    </h3>
                    <p className="mt-0.5 text-xs text-spotify-muted">
                      {t.size} documents · {Math.round(t.share * 100)}% of corpus
                      · score {t.opportunity_score.toFixed(1)}
                    </p>
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${SENTIMENT_STYLE[t.sentiment]}`}
                >
                  {t.sentiment}
                </span>
              </div>

              <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Unmet need" value={t.unmet_need} />
                <Field label="User segment" value={t.segment} />
                {t.research_question && (
                  <Field
                    label="Maps to"
                    value={t.research_question}
                    className="sm:col-span-2"
                  />
                )}
              </dl>

              {t.keywords.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {t.keywords.map((k) => (
                    <span
                      key={k}
                      className="rounded-full bg-spotify-elevated px-2 py-0.5 text-[11px] text-spotify-subtle"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              )}

              {t.example_quotes.length > 0 && (
                <div className="mt-4 border-l-2 border-spotify-green/40 pl-3">
                  <p className="mb-1 text-[11px] uppercase tracking-wide text-spotify-muted">
                    Representative quotes
                  </p>
                  <ul className="space-y-1.5">
                    {t.example_quotes.map((q, i) => (
                      <li
                        key={i}
                        className="text-sm italic leading-snug text-white/85"
                      >
                        &ldquo;{q}&rdquo;
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ol>
      </section>

      <p className="mt-10 text-center text-[11px] text-spotify-muted">
        Raw pipeline: <code>ingest/</code> · snapshot committed to{" "}
        <code>ingest/snapshots/opportunities-latest.json</code>
      </p>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-spotify-border bg-spotify-surface px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-spotify-muted">
        {label}
      </p>
      <p className="mt-0.5 text-xl font-bold text-white">{value}</p>
    </div>
  );
}

function Field({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="text-[11px] uppercase tracking-wide text-spotify-muted">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm text-white/90">{value}</dd>
    </div>
  );
}
