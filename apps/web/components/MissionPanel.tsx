"use client";

import { useMemo, useState } from "react";

import type { GenreInfo, Mission, MissionTrack } from "@/lib/types";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function trackState(t: MissionTrack): { dot: string; cls: string; note: string } {
  if (t.adopted) return { dot: "✓", cls: "text-spotify-green", note: "adopted" };
  if (t.tried) return { dot: "◐", cls: "text-amber-300", note: "in rotation" };
  return { dot: "○", cls: "text-spotify-muted", note: "" };
}

export function MissionPanel({
  mission,
  genres,
  seedGenre,
  topGenres,
  onCreate,
  onEnd,
  creating,
}: {
  mission: Mission | null;
  genres: GenreInfo[];
  seedGenre?: string | null;
  topGenres: string[];
  onCreate: (genre: string) => void;
  onEnd: () => void;
  creating: boolean;
}) {
  // suggested default: the persona's seed genre, else a genre they don't already live in
  const suggested = useMemo(() => {
    if (seedGenre) return seedGenre;
    const top = new Set(topGenres);
    const fresh = genres.find((g) => !top.has(g.genre) && g.artists >= 3);
    return fresh?.genre ?? genres[0]?.genre ?? "jazz";
  }, [seedGenre, topGenres, genres]);

  const [picked, setPicked] = useState<string>(suggested);

  // keep the picker aligned with the suggestion when the persona changes
  const [lastSuggested, setLastSuggested] = useState(suggested);
  if (suggested !== lastSuggested) {
    setLastSuggested(suggested);
    setPicked(suggested);
  }

  // ---- no active mission: setup card ----
  if (!mission) {
    return (
      <div className="rounded-xl border border-spotify-border bg-spotify-surface p-4">
        <p className="text-xs uppercase tracking-wide text-spotify-muted">
          Discovery Mission
        </p>
        <p className="mt-1 text-sm text-spotify-subtle">
          Pick a genre and Crate plans a guided <span className="text-white">3-week
          on-ramp</span> — accessible entry points first, the real thing by week 3.
        </p>

        <label className="mt-3 block text-[11px] uppercase tracking-wide text-spotify-muted">
          Get into…
        </label>
        <select
          value={picked}
          onChange={(e) => setPicked(e.target.value)}
          className="mt-1 w-full rounded-lg border border-spotify-border bg-spotify-elevated px-3 py-2 text-sm text-white outline-none focus:border-spotify-green"
        >
          {genres.map((g) => (
            <option key={g.genre} value={g.genre}>
              {cap(g.genre)} · {g.artists} artists
            </option>
          ))}
        </select>

        <button
          onClick={() => onCreate(picked)}
          disabled={creating || !picked}
          className="mt-3 w-full rounded-lg bg-spotify-green px-3 py-2 text-sm font-semibold text-black transition hover:bg-spotify-greenDark disabled:opacity-60"
        >
          {creating ? "Planning your on-ramp…" : `Start a ${cap(picked)} mission`}
        </button>
      </div>
    );
  }

  // ---- active / completed mission ----
  const { progress, target_genre, weeks } = mission;
  const done = progress.status === "completed";

  return (
    <div
      className={`rounded-xl border p-4 ${
        done
          ? "border-spotify-green/40 bg-spotify-green/5"
          : "border-spotify-border bg-spotify-surface"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-spotify-muted">
            Discovery Mission
          </p>
          <p className="mt-0.5 text-base font-semibold">
            Getting into {cap(target_genre)}
          </p>
        </div>
        <button
          onClick={onEnd}
          className="shrink-0 text-[11px] text-spotify-muted underline-offset-2 transition hover:text-white hover:underline"
        >
          End
        </button>
      </div>

      {done && (
        <div className="animate-pop-in mt-3 rounded-lg border border-spotify-green/40 bg-spotify-green/10 px-3 py-2 text-sm font-medium text-spotify-green">
          🎉 Mission complete — you&apos;re into {cap(target_genre)}.
        </div>
      )}

      {/* progress toward completion */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-spotify-subtle">
            {progress.adopted_artists}/{progress.target_artists} artists adopted
          </span>
          <span className="text-spotify-muted">{progress.percent}%</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-spotify-elevated">
          <div
            className="h-full rounded-full bg-spotify-green transition-all duration-500"
            style={{ width: `${progress.percent}%` }}
          />
        </div>
        <p className="mt-1 text-[11px] text-spotify-muted">
          {progress.tried_artists} tried · adopt {progress.target_artists} to complete
        </p>
      </div>

      {/* staged weeks */}
      <div className="mt-4 space-y-3">
        {weeks.map((w) => (
          <div key={w.week}>
            <p className="text-[11px] font-medium uppercase tracking-wide text-spotify-muted">
              Week {w.week} · <span className="text-spotify-subtle">{w.theme}</span>
            </p>
            <ul className="mt-1 space-y-1">
              {w.tracks.map((t) => {
                const s = trackState(t);
                return (
                  <li
                    key={t.id}
                    className="flex items-center justify-between gap-2 text-[12px]"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className={s.cls}>{s.dot}</span>
                      <span className="truncate text-spotify-subtle">{t.artist}</span>
                    </span>
                    {s.note && (
                      <span className={`shrink-0 text-[10px] ${s.cls}`}>{s.note}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
