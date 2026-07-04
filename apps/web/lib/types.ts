export interface User {
  id: string;
  display_name: string;
  comfort_pref: number;
  persona?: string | null;
  mission_seed_genre?: string | null;
}

export interface AudioFeatures {
  energy: number;
  valence: number;
  acousticness: number;
  tempo: number;
}

export interface Track {
  id: string;
  title: string;
  artist: string;
  artist_id: string;
  genres: string[];
  era?: string | null;
  moods: string[];
  audio_features: AudioFeatures;
  preview_url?: string | null;
}

export type Surface = "dig" | "re-serve" | "mission";

export interface DigItem {
  track: Track;
  bridge_text: string;
  shared: string[];
  surface: Surface;
  similarity?: number | null;
}

export interface DigResponse {
  greeting: string;
  items: DigItem[];
  comfort: number;
}

export interface TasteProfile {
  user_id: string;
  summary?: string | null;
  top_artists: string[];
  top_genres: string[];
}

export type Action = "served" | "played" | "skipped" | "saved";

export interface ArtistAdoption {
  artist_id: string;
  artist: string;
  status: "candidate" | "adopted";
  distinct_days: number;
  span_weeks: number;
  adopted_at?: string | null;
}

export interface AdoptionMetrics {
  user_id: string;
  adoption_rate: number;
  adopted: ArtistAdoption[];
  candidates: ArtistAdoption[];
  skip_rate: number;
  comfort_pref: number;
  surfaced_artists: number;
  tried_artists: number;
  guardrail_active: boolean;
  skip_guardrail_threshold: number;
}

export interface LoopResult {
  user_id: string;
  newly_adopted: ArtistAdoption[];
  comfort_pref: number;
  celebration?: string | null;
}

// --- Discovery Missions (Phase 7) ---
export interface MissionTrack {
  id: string;
  title: string;
  artist: string;
  artist_id: string;
  tried: boolean;
  adopted: boolean;
}

export interface MissionWeek {
  week: number;
  theme: string;
  tracks: MissionTrack[];
}

export interface MissionProgress {
  total_artists: number;
  tried_artists: number;
  adopted_artists: number;
  target_artists: number;
  percent: number;
  status: "active" | "completed";
}

export interface Mission {
  id: string;
  user_id: string;
  goal: string;
  target_genre: string;
  status: "active" | "completed" | "abandoned" | "archived";
  weeks: MissionWeek[];
  progress: MissionProgress;
  start_at?: string | null;
  end_at?: string | null;
}

export interface GenreInfo {
  genre: string;
  tracks: number;
  artists: number;
}

// --- Insights chat (grounded Q&A over the discovery backlog) ---
export type Confidence = "high" | "medium" | "low";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface InsightsAnswer {
  answer: string;
  citations: number[]; // theme ranks the answer draws from
  confidence: Confidence;
  refused: boolean;
}
