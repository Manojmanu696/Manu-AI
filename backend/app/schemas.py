from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class MediaBase(BaseModel):
    media_type: str = Field(pattern="^(movie|anime|tv|game|book)$")
    title: str = Field(min_length=1, max_length=300); description: str = ""; genres: str = ""
    personal_rating: float | None = Field(default=None, ge=1, le=10)
    sentiment: str = Field(default="neutral", pattern="^(like|dislike|neutral)$")
    status: str = Field(default="want", pattern="^(want|current|completed|dropped|on_hold)$")
    notes: str = ""; tags: str = ""; runtime: str = ""
    release_year: int | None = Field(default=None, ge=1800, le=2100)
    external_id: str = ""; external_url: str = ""; image_url: str = ""; ai_metadata: str = ""
    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str: return value.strip()
class MediaCreate(MediaBase): pass
class MediaUpdate(MediaBase): pass
class MediaOut(MediaBase):
    id: int; is_demo: bool; date_added: datetime; date_completed: datetime | None
    model_config = {"from_attributes": True}

class MemoryBase(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=3000)
    source: str = Field(default="user", pattern="^(user|inferred|chatgpt_import)$")
    confidence: float | None = Field(default=None, ge=0, le=1)
class MemoryCreate(MemoryBase): pass
class MemoryOut(MemoryBase):
    id: int; is_demo: bool; created_at: datetime
    model_config = {"from_attributes": True}

class ChatRequest(BaseModel): message: str = Field(min_length=1, max_length=4000)
class ChatResponse(BaseModel):
    answer: str; mode: str; model: str | None = None; facts: list[str]; recommendations: list[dict]
    sources: list[dict] = Field(default_factory=list); assumptions: list[str]
class CatalogueOut(BaseModel):
    id: int; media_type: str; title: str; description: str; genres: str; tags: str; release_year: int | None
    image_url: str; external_url: str; imdb_rating: float | None; public_rating: float | None; runtime: str
    intensity: str; ending_type: str; ott_india: str; seasons: int | None; episodes: int | None
    episode_duration: str; author: str; page_count: int | None; reading_length: str; gameplay_style: str
    story_focus: str; player_modes: str; difficulty: str; source_url: str; source_retrieved_at: datetime | None
    is_demo: bool; model_config = {"from_attributes": True}
class FeedbackCreate(BaseModel): action: str = Field(pattern="^(like|not_for_me|watchlist|watched)$")
class InternetQuery(BaseModel): query: str = Field(min_length=2, max_length=500)
class InternetFetch(BaseModel): url: str = Field(min_length=8, max_length=2000)

class MemoryImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    source_label: str = Field(default="chatgpt_import", max_length=80)
class MemoryImportResponse(BaseModel): imported: list[MemoryOut]; summary: str
class PersonalSnapshot(BaseModel):
    generated_at: datetime; explicit_memories: list[dict]; inferred_memories: list[dict]
    library: list[dict]; watchlist: list[dict]; instructions_for_chatgpt: str
