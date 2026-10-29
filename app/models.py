from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Naive UTC, which is what SQLite stores."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Gemini's read of how interesting this is to the reader, 0-100
    ai_score: Mapped[int | None] = mapped_column(Integer)
    ai_reason: Mapped[str | None] = mapped_column(String(300))
    # How many votes there were when it was scored, so stories can be
    # scored again once the taste has moved
    scored_votes: Mapped[int | None] = mapped_column(Integer)

    # 1: more like this, -1: less like this, 0: no vote
    vote: Mapped[int] = mapped_column(Integer, default=0, index=True)
    voted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
