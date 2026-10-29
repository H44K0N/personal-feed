import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import curator, fetcher, taste
from app.config import HIDE_BELOW, KEEP_DAYS, MIN_REFRESH_SECONDS, RUN_FETCHER
from app.database import engine, get_db
from app.models import Base, Setting, Story, utcnow
from app.sources import SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Base.metadata.create_all(engine)

STATIC = Path(__file__).resolve().parent.parent / "static"
# Most stories sent to the page
LIMIT = 400


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(fetcher.run_forever()) if RUN_FETCHER else None
    yield
    if task:
        task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


def _setting(db: Session, key: str) -> str:
    setting = db.get(Setting, key)
    return setting.value if setting else ""


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds") + "Z"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/feed")
def feed(db: Session = Depends(get_db)):
    """Recent stories, best first, each marked hidden if it scores too low."""
    now = utcnow()
    learned = taste.learn(db.scalars(select(Story).where(Story.vote != 0)).all())
    stories = db.scalars(
        select(Story)
        .where(Story.published_at >= now - timedelta(days=KEEP_DAYS))
        .order_by(Story.published_at.desc())
        .limit(LIMIT)
    ).all()
    rows = []
    for story in stories:
        score = taste.score(story, learned)
        rows.append({
            "id": story.id,
            "source": story.source,
            "title": story.title,
            "url": story.url,
            "summary": story.summary,
            "image": story.image,
            "published_at": _iso(story.published_at),
            "score": score,
            "reason": story.ai_reason,
            "vote": story.vote,
            "hidden": score < HIDE_BELOW,
            "rank": taste.rank(score, story.published_at, now),
        })
    rows.sort(key=lambda row: row["rank"], reverse=True)
    errors = set(filter(None, _setting(db, "errors").split(",")))
    refreshed = _setting(db, "refreshed_at")
    return {
        "stories": rows,
        "sources": [{"key": s.key, "name": s.name, "failed": s.key in errors} for s in SOURCES],
        "refreshed_at": refreshed + "Z" if refreshed else None,
        "ai": curator.client is not None,
        "votes": sum(1 for s in stories if s.vote),
    }


class VoteIn(BaseModel):
    vote: int = Field(ge=-1, le=1)


@app.post("/api/stories/{story_id}/vote")
def vote(story_id: int, body: VoteIn, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "Fant ikke saken.")
    story.vote = body.vote
    story.voted_at = utcnow() if body.vote else None
    db.commit()
    return {"id": story.id, "vote": story.vote}


class InterestsIn(BaseModel):
    text: str = Field(max_length=2000)


@app.get("/api/interests")
def get_interests(db: Session = Depends(get_db)):
    return {"text": _setting(db, "interests")}


@app.put("/api/interests")
def put_interests(body: InterestsIn, db: Session = Depends(get_db)):
    db.merge(Setting(key="interests", value=body.text.strip()))
    # Everything recent is read again against the new words
    for story in db.scalars(select(Story).where(Story.ai_score.is_not(None))).all():
        story.scored_votes = -curator.RESCORE_AFTER_VOTES
    db.commit()
    return {"text": body.text.strip()}


@app.post("/api/refresh")
async def refresh(db: Session = Depends(get_db)):
    last = _setting(db, "refreshed_at")
    if last and utcnow() - datetime.fromisoformat(last) < timedelta(seconds=MIN_REFRESH_SECONDS):
        raise HTTPException(429, "Feeden ble nettopp oppdatert. Prøv igjen om litt.")
    result = await fetcher.refresh_locked()
    if result is None:
        raise HTTPException(409, "Oppdaterer allerede.")
    return result


class Static(StaticFiles):
    """No caching: one reader, small files, and never an old script next to a
    new page."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if not path.startswith("fonts/"):
            response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", Static(directory=STATIC, html=True), name="static")
