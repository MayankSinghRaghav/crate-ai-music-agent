"use client";

import type { AdoptionMetrics } from "@/lib/types";

const ADOPT_DAYS = 4;
const ADOPT_WEEKS = 3;

function FunnelStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1 text-center">
      <div className="text-xl font-bold tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-spotify-muted">{label}</div>
    </div>
  );
}

export function AdoptionPanel({
  metrics,
  onSimulate,
  simulating,
}: {
  metrics: AdoptionMetrics | null;
  onSimulate: () => void;
  simulating: boolean;
}) {
  const rate = metrics ? Math.round(metrics.adoption_rate * 100) : 0;
  const skip = metrics ? Math.round(metrics.skip_rate * 100) : 0;
  const threshold = Math.round((metrics?.skip_guardrail_threshold ?? 0.6) * 100);
  const guardrail = metrics?.guardrail_active ?? false;
  const comfort = Math.round((metrics?.comfort_pref ?? 0.5) * 100);

  return (
    <div className="rounded-xl border border-spotify-border bg-spotify-surface p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-xs uppercase tracking-wide text-spotify-muted">North Star</p>
        <p className="text-[11px] text-spotify-muted">adopted ÷ surfaced</p>
      </div>
      <div className="mt-1 flex items-end gap-2">
        <span className="text-4xl font-bold text-spotify-green">{rate}%</span>
        <span className="pb-1 text-sm text-spotify-subtle">Discovery Adoption Rate</span>
      </div>

      {/* discovery funnel — surfaced → tried → adopted */}
      <div className="mt-3 flex items-center rounded-lg border border-spotify-border bg-spotify-elevated/40 px-2 py-2">
        <FunnelStat label="Surfaced" value={metrics?.surfaced_artists ?? 0} />
        <span className="px-1 text-spotify-muted">→</span>
        <FunnelStat label="Tried" value={metrics?.tried_artists ?? 0} />
        <span className="px-1 text-spotify-muted">→</span>
        <div className="flex-1 text-center">
          <div className="text-xl font-bold tabular-nums text-spotify-green">
            {metrics?.adopted.length ?? 0}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-spotify-green/70">Adopted</div>
        </div>
      </div>

      <button
        onClick={onSimulate}
        disabled={simulating}
        className="mt-3 w-full rounded-lg bg-spotify-green px-3 py-2 text-sm font-semibold text-black transition hover:bg-spotify-greenDark disabled:opacity-60"
      >
        {simulating ? "Simulating…" : "▶ Simulate 3 weeks of listening"}
      </button>
      <p className="mt-1.5 text-[11px] text-spotify-muted">
        Inserts unprompted listens for tracks you played, advancing a demo clock so
        adoption can cross its threshold live.
      </p>

      {metrics && metrics.adopted.length > 0 && (
        <div className="mt-4">
          <p className="mb-1.5 text-xs font-medium text-spotify-subtle">
            Adopted ({metrics.adopted.length})
          </p>
          <ul className="space-y-1.5">
            {metrics.adopted.map((a) => (
              <li
                key={a.artist_id}
                className="flex items-center justify-between rounded-lg bg-spotify-green/10 px-2.5 py-1.5"
              >
                <span className="flex items-center gap-2 text-sm">
                  <span className="text-spotify-green">✓</span> {a.artist}
                </span>
                <span className="text-[11px] text-spotify-subtle">
                  {a.distinct_days}d · {a.span_weeks}w
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {metrics && metrics.candidates.length > 0 && (
        <div className="mt-4">
          <p className="mb-1.5 text-xs font-medium text-spotify-subtle">
            In rotation, not yet adopted ({metrics.candidates.length})
          </p>
          <ul className="space-y-2">
            {metrics.candidates.slice(0, 5).map((c) => {
              const pct = Math.min(100, Math.round((c.distinct_days / ADOPT_DAYS) * 100));
              return (
                <li key={c.artist_id}>
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="text-spotify-subtle">{c.artist}</span>
                    <span className="text-spotify-muted">
                      {c.distinct_days}/{ADOPT_DAYS}d
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-spotify-elevated">
                    <div className="h-full rounded-full bg-spotify-green/60" style={{ width: `${pct}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* engagement guardrail */}
      <div
        className={`mt-4 rounded-lg border px-3 py-2.5 ${
          guardrail
            ? "border-amber-400/40 bg-amber-400/10"
            : "border-spotify-border bg-spotify-elevated/30"
        }`}
      >
        <div className="flex items-center justify-between text-[12px]">
          <span className="font-medium text-spotify-subtle">Engagement guardrail</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              guardrail ? "bg-amber-400/20 text-amber-300" : "bg-spotify-elevated text-spotify-muted"
            }`}
          >
            {guardrail ? "ACTIVE" : "idle"}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px]">
          <span className="text-spotify-muted">Skip rate</span>
          <span className={guardrail ? "text-amber-300" : "text-spotify-subtle"}>
            {skip}% <span className="text-spotify-muted">/ {threshold}% limit</span>
          </span>
        </div>
        <div className="mt-1 flex items-center justify-between text-[11px]">
          <span className="text-spotify-muted">Comfort default</span>
          <span className="text-spotify-subtle">{comfort}%</span>
        </div>
        <p className="mt-1.5 text-[11px] text-spotify-muted">
          {guardrail
            ? "Too many skips — Spotify pulled your dial back toward Comfort for safer picks."
            : "Keeps stretch in check: if you start skipping a lot, Spotify eases the dial back."}
        </p>
      </div>

      <p className="mt-3 text-[11px] text-spotify-muted">
        Adoption = played ≥{ADOPT_DAYS} distinct days across ≥{ADOPT_WEEKS} weeks,
        unprompted.
      </p>
    </div>
  );
}
