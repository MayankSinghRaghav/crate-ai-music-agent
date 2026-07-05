"""Pydantic models — the JSON shapes the frontend builds against."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Surface = Literal["dig", "re-serve", "mission"]
Action = Literal["served", "played", "skipped", "saved"]
Sentiment = Literal["up", "down"]


class AudioFeatures(BaseModel):
    energy: float = 0.5
    valence: float = 0.5
    acousticness: float = 0.5
    tempo: float = 110.0


class Track(BaseModel):
    id: str
    title: str
    artist: str
    artist_id: str
    genres: list[str] = []
    era: Optional[str] = None
    moods: list[str] = []
    audio_features: AudioFeatures = Field(default_factory=AudioFeatures)
    preview_url: Optional[str] = None


class User(BaseModel):
    id: str
    display_name: str
    comfort_pref: float = 0.5
    persona: Optional[str] = None
    mission_seed_genre: Optional[str] = None


class TasteProfile(BaseModel):
    user_id: str
    summary: Optional[str] = None
    top_artists: list[str] = []
    top_genres: list[str] = []


class DigItem(BaseModel):
    track: Track
    bridge_text: str
    shared: list[str] = []
    surface: Surface = "dig"
    similarity: Optional[float] = None


class DigResponse(BaseModel):
    greeting: str
    items: list[DigItem] = []
    comfort: float = 0.5


# --- request bodies ---
class EventIn(BaseModel):
    user_id: str
    track_id: str
    action: Action


class FeedbackIn(BaseModel):
    user_id: str
    track_id: str
    sentiment: Sentiment
    reason: Optional[str] = None


# --- adoption / metrics (Phase 6) ---
class ArtistAdoption(BaseModel):
    artist_id: str
    artist: str
    status: Literal["candidate", "adopted"]
    distinct_days: int = 0
    span_weeks: float = 0.0
    adopted_at: Optional[str] = None


class AdoptionMetrics(BaseModel):
    user_id: str
    adoption_rate: float = 0.0
    adopted: list[ArtistAdoption] = []
    candidates: list[ArtistAdoption] = []
    skip_rate: float = 0.0
    comfort_pref: float = 0.5
    # discovery funnel (each maps directly to a DB query)
    surfaced_artists: int = 0   # distinct artists Crate has surfaced
    tried_artists: int = 0      # of those, how many the listener actually played
    # engagement guardrail
    guardrail_active: bool = False
    skip_guardrail_threshold: float = 0.6


class LoopResult(BaseModel):
    user_id: str
    newly_adopted: list[ArtistAdoption] = []
    comfort_pref: float = 0.5
    celebration: Optional[str] = None


# --- Discovery Missions (Phase 7) ---
class MissionTrack(BaseModel):
    id: str
    title: str
    artist: str
    artist_id: str
    tried: bool = False      # played at least once (runtime/sim)
    adopted: bool = False    # crossed the adoption threshold


class MissionWeek(BaseModel):
    week: int
    theme: str
    tracks: list[MissionTrack] = []


class MissionProgress(BaseModel):
    total_artists: int = 0
    tried_artists: int = 0
    adopted_artists: int = 0
    target_artists: int = 0      # adoptions needed to complete the mission
    percent: int = 0             # 0-100, toward completion
    status: Literal["active", "completed"] = "active"


class Mission(BaseModel):
    id: str
    user_id: str
    goal: str
    target_genre: str
    status: Literal["active", "completed", "abandoned", "archived"] = "active"
    weeks: list[MissionWeek] = []
    progress: MissionProgress = Field(default_factory=MissionProgress)
    start_at: Optional[str] = None
    end_at: Optional[str] = None


class MissionCreateIn(BaseModel):
    user_id: str
    target_genre: str


class GenreInfo(BaseModel):
    genre: str
    tracks: int
    artists: int


# --- Insights chat (grounded Q&A over the discovery backlog) ---
Confidence = Literal["high", "medium", "low"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class InsightsAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be blank")
        return v


class InsightsAnswer(BaseModel):
    answer: str
    citations: list[int] = []          # theme ranks the answer draws from
    confidence: Confidence = "medium"
    refused: bool = False              # true when unanswerable from the backlog


class ClassifyIn(BaseModel):
    review: str = Field(min_length=1, max_length=1000)

    @field_validator("review")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("review must not be blank")
        return v


class Classification(BaseModel):
    frustration_type: str
    job_to_be_done: str
    segment: str
    intensity: Literal["low", "medium", "high"] = "medium"


class InsightsSummary(BaseModel):
    summary: str
    themes_analysed: int = 0
    reviews_analysed: int = 0
    generated: bool = False            # true when written by the LLM (vs template)
