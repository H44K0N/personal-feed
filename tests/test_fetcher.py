from datetime import timedelta

from app import fetcher
from app.config import KEEP_DAYS
from app.models import Setting, Story, utcnow
from app.sources import Item, SOURCES
from tests.helpers import add_story


def item(url, title="Sak", hours_old=1):
    return Item(url=url, title=title, summary="", image=None, published_at=utcnow() - timedelta(hours=hours_old))


def test_store_adds_new_stories_once(db):
    assert fetcher.store(db, {"nrk": [item("https://e.com/1"), item("https://e.com/2")]}) == 2
    # the same story from a second fetch, or twice in one, is not added again
    assert fetcher.store(db, {"nrk": [item("https://e.com/1")], "vg": [item("https://e.com/3"), item("https://e.com/3")]}) == 1
    assert db.query(Story).count() == 3


def test_store_skips_old_items_and_clamps_future_dates(db):
    fetcher.store(db, {"tu": [item("https://e.com/old", hours_old=24 * (KEEP_DAYS + 1)), item("https://e.com/future", hours_old=-48)]})
    stories = db.query(Story).all()
    assert [s.url for s in stories] == ["https://e.com/future"]
    assert stories[0].published_at <= utcnow()


def test_prune_keeps_voted_stories(db):
    old = utcnow() - timedelta(days=KEEP_DAYS + 1)
    add_story(db, "Gammel", fetched_at=old)
    add_story(db, "Gammel, likt", fetched_at=old, vote=1)
    add_story(db, "Gammel, mislikt", fetched_at=old, vote=-1)
    add_story(db, "Ny")
    assert fetcher.prune(db) == 1
    assert sorted(s.title for s in db.query(Story)) == ["Gammel, likt", "Gammel, mislikt", "Ny"]


def test_one_broken_feed_does_not_stop_the_others(db, monkeypatch):
    def fetch(source):
        if source.key == "reddit":
            raise OSError("HTTP Error 429: Too Many Requests")
        return [item(f"https://e.com/{source.key}")]

    monkeypatch.setattr(fetcher, "fetch", fetch)
    result = fetcher.refresh(db)
    assert result["added"] == len(SOURCES) - 1
    assert result["failed"] == ["reddit"]
    assert db.get(Setting, "errors").value == "reddit"
    assert db.get(Setting, "refreshed_at").value
