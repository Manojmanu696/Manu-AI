from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class MediaItem(Base):
    __tablename__ = "media_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_type: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    genres: Mapped[str] = mapped_column(String(600), default="")
    personal_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    status: Mapped[str] = mapped_column(String(30), default="want")
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(600), default="")
    runtime: Mapped[str] = mapped_column(String(80), default="")
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_id: Mapped[str] = mapped_column(String(200), default="")
    external_url: Mapped[str] = mapped_column(String(1000), default="")
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    ai_metadata: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    date_added: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    date_completed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="user")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CatalogueItem(Base):
    """A discovery candidate. Personal interaction belongs in MediaItem, never here."""
    __tablename__ = "catalogue_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_type: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    genres: Mapped[str] = mapped_column(String(600), default="")
    tags: Mapped[str] = mapped_column(String(600), default="")
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    external_id: Mapped[str] = mapped_column(String(200), default="")
    external_url: Mapped[str] = mapped_column(String(1000), default="")
    imdb_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    public_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    runtime: Mapped[str] = mapped_column(String(80), default="")
    intensity: Mapped[str] = mapped_column(String(50), default="")
    ending_type: Mapped[str] = mapped_column(String(80), default="")
    ott_india: Mapped[str] = mapped_column(String(400), default="")
    seasons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_duration: Mapped[str] = mapped_column(String(80), default="")
    author: Mapped[str] = mapped_column(String(300), default="")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reading_length: Mapped[str] = mapped_column(String(80), default="")
    gameplay_style: Mapped[str] = mapped_column(String(200), default="")
    story_focus: Mapped[str] = mapped_column(String(200), default="")
    player_modes: Mapped[str] = mapped_column(String(200), default="")
    difficulty: Mapped[str] = mapped_column(String(80), default="")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    source_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalogue_item_id: Mapped[int] = mapped_column(ForeignKey("catalogue_items.id"), index=True)
    action: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ResearchSource(Base):
    __tablename__ = "research_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalogue_item_id: Mapped[int | None] = mapped_column(ForeignKey("catalogue_items.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="")
    query: Mapped[str] = mapped_column(String(1000), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(1000))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
