from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class MediaBase(BaseModel):
    media_type: str = Field(pattern="^(movie|anime|tv|game|book)$")
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    genres: str = ""
    personal_rating: float | None = Field(default=None, ge=1, le=10)
    sentiment: str = Field(default="neutral", pattern="^(like|dislike|neutral)$")
    status: str = Field(default="want", pattern="^(want|current|completed|dropped|on_hold)$")
    notes: str = ""
    tags: str = ""
    runtime: str = ""
    release_year: int | None = Field(default=None, ge=1800, le=2100)
    external_id: str = ""
    external_url: str = ""
    image_url: str = ""
    ai_metadata: str = ""

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return value.strip()


class MediaCreate(MediaBase):
    pass


class MediaUpdate(MediaBase):
    pass


class MediaOut(MediaBase):
    id: int
    is_demo: bool
    date_added: datetime
    date_completed: datetime | None
    model_config = {"from_attributes": True}


class MemoryBase(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=3000)
    source: str = Field(default="user", pattern="^(user|inferred)$")
    confidence: float | None = Field(default=None, ge=0, le=1)


class MemoryCreate(MemoryBase):
    pass


class MemoryOut(MemoryBase):
    id: int
    is_demo: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    mode: str
    facts: list[str]
    recommendations: list[dict]
    assumptions: list[str]

