"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AdoptionPanel } from "@/components/AdoptionPanel";
import { ComfortDial } from "@/components/ComfortDial";
import { DigCard } from "@/components/DigCard";
import { FeedbackModal } from "@/components/FeedbackModal";
import Link from "next/link";

import { Logo } from "@/components/Logo";
import { MissionPanel } from "@/components/MissionPanel";
import { UserSwitcher } from "@/components/UserSwitcher";
import { api } from "@/lib/api";
import type {
  Action,
  AdoptionMetrics,
  DigItem,
  DigResponse,
  GenreInfo,
  Mission,
  TasteProfile,
  User,
} from "@/lib/types";

export default function Home() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [taste, setTaste] = useState<TasteProfile | null>(null);
  const [dig, setDig] = useState<DigResponse | null>(null);
  const [comfort, setComfort] = useState(0.5);
  const [loading, setLoading] = useState(false);
  const [apiDown, setApiDown] = useState(false);
  const [actions, setActions] = useState<Record<string, Action>>({});
  const [feedbackItem, setFeedbackItem] = useState<DigItem | null>(null);
  const [metrics, setMetrics] = useState<AdoptionMetrics | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [celebration, setCelebration] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mission, setMission] = useState<Mission | null>(null);
  const [genres, setGenres] = useState<GenreInfo[]>([]);
  const [creatingMission, setCreatingMission] = useState(false);

  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadMetrics = useCallback(async (userId: string) => {
    try {
      setMetrics(await api.metrics(userId));
    } catch {
      /* metrics are best-effort */
    }
  }, []);

  const loadMission = useCallback(async (userId: string) => {
    try {
      setMission(await api.mission(userId));
    } catch {
      setMission(null);
    }
  }, []);

  const loadDig = useCallback(async (userId: string, c: number) => {
    setLoading(true);
    try {
      const data = await api.dig(userId, c);
      setDig(data);
      setApiDown(false);
    } catch {
      setApiDown(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // bootstrap: users + available mission genres
  useEffect(() => {
    (async () => {
      try {
        const us = await api.users();
        setUsers(us);
        api.genres().then(setGenres).catch(() => setGenres([]));
        const saved =
          typeof window !== "undefined" ? localStorage.getItem("crate.user") : null;
        const initial = us.find((u) => u.id === saved) ?? us[0];
        if (initial) selectUser(initial, us);
      } catch {
        setApiDown(true);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectUser(u: User, list: User[] = users) {
    setSelectedId(u.id);
    setActions({});
    setComfort(u.comfort_pref);
    setCelebration(null);
    setNotice(null);
    if (typeof window !== "undefined") localStorage.setItem("crate.user", u.id);
    api.taste(u.id).then(setTaste).catch(() => setTaste(null));
    loadDig(u.id, u.comfort_pref);
    loadMetrics(u.id);
    loadMission(u.id);
    void list;
  }

  async function onSimulate() {
    if (!selectedId) return;
    setSimulating(true);
    try {
      const res = await api.simulate(selectedId, 4, 1);
      if (res.celebration) setCelebration(res.celebration);
      await loadMetrics(selectedId);
      await loadMission(selectedId); // mission progress advances with adoption
      await loadDig(selectedId, comfort); // re-serve / mission / adapted picks may change
    } catch {
      /* ignore */
    } finally {
      setSimulating(false);
    }
  }

  async function onCreateMission(genre: string) {
    if (!selectedId) return;
    setCreatingMission(true);
    try {
      const m = await api.createMission(selectedId, genre);
      setMission(m);
      await loadDig(selectedId, comfort); // mission picks now appear in the dig
    } catch {
      /* ignore */
    } finally {
      setCreatingMission(false);
    }
  }

  async function onEndMission() {
    if (!selectedId) return;
    setMission(null);
    try {
      await api.endMission(selectedId);
      await loadDig(selectedId, comfort);
    } catch {
      /* ignore */
    }
  }

  function onComfortChange(v: number) {
    setComfort(v);
    setNotice(null); // manual override clears the guardrail notice
    if (!selectedId) return;
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => loadDig(selectedId, v), 350);
  }

  async function act(item: DigItem, action: Action) {
    if (!selectedId) return;
    const prev = actions[item.track.id];
    setActions((a) => ({ ...a, [item.track.id]: action })); // optimistic
    try {
      await api.event(selectedId, item.track.id, action);
      if (action === "skipped") {
        // let the agent react: a high skip-rate trips the engagement guardrail,
        // which nudges comfort back toward safer picks. Reflect it immediately.
        const res = await api.loopTick(selectedId);
        if (res.comfort_pref < comfort) {
          setComfort(res.comfort_pref);
          setNotice(
            `Engagement guardrail: you were skipping a lot, so Crate eased your dial back to ${Math.round(
              res.comfort_pref * 100
            )}% comfort for safer picks.`
          );
          await loadDig(selectedId, res.comfort_pref);
        }
      }
      loadMetrics(selectedId); // funnel / skip-rate / candidates update as you act
    } catch {
      // revert instead of silently pretending the action stuck
      setActions((a) => ({ ...a, [item.track.id]: prev as Action }));
      setNotice(`Couldn't save that ${action} — the API didn't respond. Try again.`);
    }
  }

  async function submitFeedback(reason: string) {
    if (!selectedId || !feedbackItem) return;
    const item = feedbackItem;
    setFeedbackItem(null);
    try {
      await api.feedback(selectedId, item.track.id, "down", reason || undefined);
    } catch {
      /* ignore */
    }
    // refetch so the down-voted artist disappears — visible adaptation
    loadDig(selectedId, comfort);
  }

  const selectedUser = users.find((u) => u.id === selectedId) ?? null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      {/* top bar */}
      <header className="flex items-center justify-between">
        <Logo />
        <div className="flex items-center gap-2 text-xs">
          <Link
            href="/insights"
            className="rounded-full border border-spotify-border bg-spotify-surface px-2.5 py-1 text-spotify-subtle transition hover:text-white"
          >
            Insights →
          </Link>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${
              apiDown
                ? "border-red-500/40 text-red-400"
                : "border-spotify-border text-spotify-subtle"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${apiDown ? "bg-red-500" : "bg-spotify-green"}`}
            />
            {apiDown ? "API offline" : "connected"}
          </span>
        </div>
      </header>

      {apiDown && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          Can&apos;t reach the Crate API at <code>{api.base}</code>. Start it with{" "}
          <code>uvicorn app.main:app --port 8000</code> and seed via{" "}
          <code>POST /dev/seed</code>.
        </div>
      )}

      {/* persona switcher */}
      <section className="mt-6">
        <p className="mb-2 text-xs uppercase tracking-wide text-spotify-muted">
          Listening as
        </p>
        <UserSwitcher users={users} selectedId={selectedId} onSelect={(id) => {
          const u = users.find((x) => x.id === id);
          if (u) selectUser(u);
        }} />
      </section>

      {/* main grid */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* dig column */}
        <div className="lg:col-span-2">
          <h1 className="text-2xl font-bold tracking-tight">
            {dig?.greeting ?? "Today's Dig"}
          </h1>
          {taste?.summary && (
            <p className="mt-1 text-sm text-spotify-subtle">
              <span className="text-spotify-muted">Your taste:</span> {taste.summary}
            </p>
          )}

          {celebration && (
            <div className="animate-pop-in mt-4 flex items-center justify-between rounded-xl border border-spotify-green/40 bg-spotify-green/10 px-4 py-3">
              <p className="text-sm font-medium text-spotify-green">{celebration}</p>
              <button
                onClick={() => setCelebration(null)}
                className="text-spotify-subtle transition hover:text-white"
                aria-label="dismiss"
              >
                ✕
              </button>
            </div>
          )}

          {notice && (
            <div className="animate-pop-in mt-4 flex items-center justify-between gap-3 rounded-xl border border-amber-400/40 bg-amber-400/10 px-4 py-3">
              <p className="text-sm font-medium text-amber-200">⚖️ {notice}</p>
              <button
                onClick={() => setNotice(null)}
                className="shrink-0 text-spotify-subtle transition hover:text-white"
                aria-label="dismiss"
              >
                ✕
              </button>
            </div>
          )}

          <div className="mt-5 space-y-3">
            {loading && !dig
              ? Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
              : dig && dig.items.length > 0
              ? dig.items.map((item, i) => (
                  <DigCard
                    key={item.track.id}
                    item={item}
                    index={i}
                    action={actions[item.track.id]}
                    onPlay={() => act(item, "played")}
                    onSkip={() => act(item, "skipped")}
                    onSave={() => act(item, "saved")}
                    onWhy={() => setFeedbackItem(item)}
                  />
                ))
              : dig && (
                  <div className="rounded-xl border border-spotify-border bg-spotify-surface p-8 text-center text-spotify-subtle">
                    No fresh picks at this setting. Try pulling the dial back toward
                    Comfort.
                  </div>
                )}
          </div>
        </div>

        {/* control column */}
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <ComfortDial value={comfort} onChange={onComfortChange} />

          <MissionPanel
            mission={mission}
            genres={genres}
            seedGenre={selectedUser?.mission_seed_genre}
            topGenres={taste?.top_genres ?? []}
            onCreate={onCreateMission}
            onEnd={onEndMission}
            creating={creatingMission}
          />

          <AdoptionPanel
            metrics={metrics}
            onSimulate={onSimulate}
            simulating={simulating}
          />

          {selectedUser?.persona && (
            <div className="rounded-xl border border-spotify-border bg-spotify-surface p-4">
              <p className="text-xs uppercase tracking-wide text-spotify-muted">
                Persona
              </p>
              <p className="mt-1 text-sm text-spotify-subtle">{selectedUser.persona}</p>
              {taste && taste.top_genres.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {taste.top_genres.map((g) => (
                    <span
                      key={g}
                      className="rounded-full bg-spotify-elevated px-2 py-0.5 text-[11px] text-spotify-subtle"
                    >
                      {g}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </aside>
      </section>

      {feedbackItem && (
        <FeedbackModal
          item={feedbackItem}
          onClose={() => setFeedbackItem(null)}
          onSubmit={submitFeedback}
        />
      )}
    </main>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-spotify-border bg-spotify-card p-4">
      <div className="h-4 w-1/3 animate-pulse rounded bg-spotify-elevated" />
      <div className="mt-2 h-3 w-1/4 animate-pulse rounded bg-spotify-elevated" />
      <div className="mt-3 h-12 w-full animate-pulse rounded bg-spotify-elevated" />
    </div>
  );
}
