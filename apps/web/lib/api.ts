import type {
  AdoptionMetrics,
  Action,
  ChatTurn,
  DigResponse,
  GenreInfo,
  InsightsAnswer,
  LoopResult,
  Mission,
  TasteProfile,
  User,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function post(path: string, body: unknown) {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  base: API_BASE,

  health: () => fetch(`${API_BASE}/health`).then(asJson<{ status: string }>),

  users: () => fetch(`${API_BASE}/users`).then(asJson<User[]>),

  taste: (userId: string) =>
    fetch(`${API_BASE}/taste/${userId}`).then(asJson<TasteProfile>),

  dig: (userId: string, comfort: number) =>
    fetch(
      `${API_BASE}/dig?user_id=${encodeURIComponent(userId)}&comfort=${comfort}`
    ).then(asJson<DigResponse>),

  event: (userId: string, trackId: string, action: Action) =>
    post("/events", { user_id: userId, track_id: trackId, action }).then(
      asJson<{ ok: boolean }>
    ),

  feedback: (
    userId: string,
    trackId: string,
    sentiment: "up" | "down",
    reason?: string
  ) =>
    post("/feedback", {
      user_id: userId,
      track_id: trackId,
      sentiment,
      reason,
    }).then(asJson<{ ok: boolean }>),

  // Phase 6
  metrics: (userId: string) =>
    fetch(`${API_BASE}/metrics/adoption?user_id=${encodeURIComponent(userId)}`).then(
      asJson<AdoptionMetrics>
    ),

  simulate: (userId: string, days: number, plays: number) =>
    post(
      `/dev/simulate?user_id=${encodeURIComponent(userId)}&days=${days}&plays=${plays}`,
      {}
    ).then(asJson<LoopResult>),

  loopTick: (userId: string) =>
    post("/loop/tick", { user_id: userId }).then(asJson<LoopResult>),

  reset: (userId: string) =>
    post(`/dev/reset?user_id=${encodeURIComponent(userId)}`, {}).then(
      asJson<{ ok: boolean }>
    ),

  // Phase 7 — Discovery Missions
  genres: () => fetch(`${API_BASE}/catalog/genres`).then(asJson<GenreInfo[]>),

  mission: (userId: string) =>
    fetch(`${API_BASE}/missions/${encodeURIComponent(userId)}`).then(
      asJson<Mission | null>
    ),

  createMission: (userId: string, targetGenre: string) =>
    post("/missions", { user_id: userId, target_genre: targetGenre }).then(
      asJson<Mission>
    ),

  endMission: (userId: string) =>
    fetch(`${API_BASE}/missions/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    }).then(asJson<{ ok: boolean; ended: boolean }>),

  // Insights grounded chat — answers only from the discovery backlog.
  askInsights: (question: string, history: ChatTurn[]) =>
    post("/insights/ask", { question, history }).then(asJson<InsightsAnswer>),

  // Resolve a 30s audio preview for a track (null when none is available).
  preview: (trackId: string) =>
    fetch(`${API_BASE}/catalog/preview/${encodeURIComponent(trackId)}`).then(
      asJson<{ track_id: string; preview_url: string | null }>
    ),
};
