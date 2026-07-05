"use client";

import { useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Action, DigItem } from "@/lib/types";

const SURFACE_BADGE: Record<string, { label: string; cls: string }> = {
  "re-serve": { label: "Back for round two", cls: "bg-amber-500/15 text-amber-300" },
  mission: { label: "Mission pick", cls: "bg-violet-500/15 text-violet-300" },
};

// Only one preview should sound at a time across all cards.
let currentAudio: HTMLAudioElement | null = null;

export function DigCard({
  item,
  action,
  index,
  onPlay,
  onSkip,
  onSave,
  onWhy,
}: {
  item: DigItem;
  action: Action | undefined;
  index: number;
  onPlay: () => void;
  onSkip: () => void;
  onSave: () => void;
  onWhy: () => void;
}) {
  const { track, bridge_text, shared, surface } = item;
  const badge = SURFACE_BADGE[surface];
  const skipped = action === "skipped";
  const played = action === "played";
  const saved = action === "saved";

  // audio preview state: undefined = not yet resolved, null = no preview found
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null | undefined>(
    track.preview_url ?? undefined
  );
  const [playing, setPlaying] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);

  async function handlePlay() {
    onPlay(); // always log the "played" signal (drives adoption metrics)

    const el = audioRef.current;
    if (!el) return;
    if (playing) {
      el.pause();
      return;
    }

    // resolve the preview URL on first play
    let url = previewUrl;
    if (url === undefined) {
      setLoadingPreview(true);
      try {
        url = (await api.preview(track.id)).preview_url;
      } catch {
        url = null;
      } finally {
        setPreviewUrl(url ?? null);
        setLoadingPreview(false);
      }
    }
    if (!url) return; // no preview — button already logged the play

    if (currentAudio && currentAudio !== el) currentAudio.pause();
    currentAudio = el;
    el.src = url;
    el.play().catch(() => setPlaying(false));
  }

  const playLabel = loadingPreview
    ? "Loading…"
    : playing
    ? "Pause"
    : played
    ? "Play again"
    : "Play";

  return (
    <div
      className={`animate-fade-up rounded-xl border border-spotify-border bg-spotify-card p-4 transition ${
        skipped ? "opacity-40" : "hover:border-spotify-muted"
      }`}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-base font-semibold">{track.title}</h3>
            {badge && (
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.cls}`}>
                {badge.label}
              </span>
            )}
          </div>
          <p className="truncate text-sm text-spotify-subtle">{track.artist}</p>
        </div>
        <div className="flex shrink-0 gap-2 text-[11px] text-spotify-muted">
          {track.genres.slice(0, 1).map((g) => (
            <span key={g} className="rounded-full bg-spotify-elevated px-2 py-0.5">
              {g}
            </span>
          ))}
          {track.era && (
            <span className="rounded-full bg-spotify-elevated px-2 py-0.5">{track.era}</span>
          )}
        </div>
      </div>

      {/* the bridge — the product's whole point */}
      <div className="mt-3 rounded-lg border-l-2 border-spotify-green bg-spotify-green/5 px-3 py-2">
        <p className="text-sm leading-snug text-white/90">{bridge_text}</p>
        {shared.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {shared.map((s) => (
              <span
                key={s}
                className="rounded-full bg-spotify-green/15 px-2 py-0.5 text-[10px] font-medium text-spotify-green"
              >
                {s}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={handlePlay}
          disabled={loadingPreview}
          aria-label={playing ? "Pause preview" : "Play preview"}
          className="flex items-center gap-1.5 rounded-full bg-spotify-green px-3 py-1.5 text-sm font-semibold text-black transition hover:bg-spotify-greenDark disabled:opacity-70"
        >
          <span aria-hidden>{playing ? "⏸" : "▶"}</span> {playLabel}
        </button>
        {previewUrl === null && (
          <span className="text-[11px] text-spotify-muted">No 30-sec preview</span>
        )}
        <audio
          ref={audioRef}
          preload="none"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
        />
        <button
          onClick={onSave}
          className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition ${
            saved
              ? "border-spotify-green text-spotify-green"
              : "border-spotify-border text-spotify-subtle hover:text-white"
          }`}
        >
          <span aria-hidden>{saved ? "♥" : "♡"}</span> {saved ? "Saved" : "Save"}
        </button>
        <button
          onClick={onSkip}
          className="flex items-center gap-1.5 rounded-full border border-spotify-border px-3 py-1.5 text-sm text-spotify-subtle transition hover:text-white"
        >
          <span aria-hidden>⏭</span> Skip
        </button>
        <button
          onClick={onWhy}
          className="ml-auto text-xs text-spotify-muted underline-offset-2 transition hover:text-white hover:underline"
        >
          tell me why
        </button>
      </div>
    </div>
  );
}
