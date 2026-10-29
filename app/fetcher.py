"""Fetch every feed, store new stories, drop old ones, then have Gemini score."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import logging
import urllib.request

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import curator
from app.config import KEEP_DAYS, REFRESH_MINUTES
from app.database import SessionLocal
from app.models import Setting, Story, utcnow
from app.sources import SOURCES, Item, Source, parse

log = logging.getLogger(__name__)

USER_AGENT = "personal-feed/0.1 (a one-reader RSS reader)"
TIMEOUT = 15
MAX_BYTES = 5_000_000


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(MAX_BYTES)


def fetch(source: Source) -> list[Item]:
    return parse(download(source.url))


def fetch_all() -> tuple[dict[str, list[Item]], dict[str, str]]:
    """Every source's items, fetched side by side, and the error of each that
    failed. One broken feed never stops the others."""
    items, errors = {}, {}
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        futures = {source.key: pool.submit(fetch, source) for source in SOURCES}
    for key, future in futures.items():
        try:
            items[key] = future.result()
        except Exception as error:
            log.warning("Could not fetch %s: %s", key, error)
            errors[key] = str(error)[:200]
    return items, errors


def store(db: Session, items: dict[str, list[Item]]) -> int:
    """Add stories not seen before (by URL). Returns how many were new."""
    known = set(db.scalars(select(Story.url)).all())
    now = utcnow()
    too_old = now - timedelta(days=KEEP_DAYS)
    added = 0
    for key, found in items.items():
        for item in found:
            if item.url in known or item.published_at < too_old:
                continue
            known.add(item.url)
            db.add(Story(
                source=key, url=item.url, title=item.title, summary=item.summary,
                # A date in the future would keep a story on top for days
                image=item.image, published_at=min(item.published_at, now),
            ))
            added += 1
    db.commit()
    return added


def prune(db: Session) -> int:
    cutoff = utcnow() - timedelta(days=KEEP_DAYS)
    result = db.execute(delete(Story).where(Story.vote == 0).where(Story.fetched_at < cutoff))
    db.commit()
    return result.rowcount


def _remember(db: Session, key: str, value: str):
    setting = db.get(Setting, key) or Setting(key=key)
    setting.value = value
    db.merge(setting)
    db.commit()


def refresh(db: Session) -> dict:
    items, errors = fetch_all()
    added = store(db, items)
    pruned = prune(db)
    scored = curator.curate(db)
    _remember(db, "refreshed_at", utcnow().isoformat(timespec="seconds"))
    _remember(db, "errors", ",".join(sorted(errors)))
    log.info("Refreshed: %d new, %d pruned, %d scored, failed: %s", added, pruned, scored, errors or "none")
    return {"added": added, "pruned": pruned, "scored": scored, "failed": sorted(errors)}


def refresh_now() -> dict:
    db = SessionLocal()
    try:
        return refresh(db)
    finally:
        db.close()


lock = asyncio.Lock()


async def refresh_locked() -> dict | None:
    """One refresh at a time; returns None if one was already running."""
    if lock.locked():
        return None
    async with lock:
        return await asyncio.to_thread(refresh_now)


async def run_forever():
    while True:
        try:
            await refresh_locked()
        except Exception:
            log.exception("Refresh failed")
        await asyncio.sleep(REFRESH_MINUTES * 60)
