from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
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
