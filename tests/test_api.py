from datetime import timedelta

from app import fetcher
from app.config import HIDE_BELOW
from app.models import Setting, Story, utcnow
from tests.helpers import add_story


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_page_and_assets_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert '<script src="/feed.js">' in page.text
    assert page.headers["cache-control"] == "no-cache"
    for path in ("/feed.js", "/style.css", "/favicon.svg", "/fonts/Libron-Regular.woff2"):
        assert client.get(path).status_code == 200, path


def test_page_builds_cards_without_inner_html():
    with open("static/feed.js", encoding="utf-8") as script:
        assert "innerHTML" not in script.read()


def test_feed_lists_stories_best_first(client, db):
    add_story(db, "Middels", ai_score=50, hours_old=1)
    add_story(db, "God", ai_score=90, hours_old=2)
    add_story(db, "Støy", ai_score=10, hours_old=1, ai_reason="Sport, som du sjelden leser.")
    data = client.get("/api/feed").json()
    titles = [s["title"] for s in data["stories"]]
    assert titles == ["God", "Middels", "Støy"]
    noise = data["stories"][2]
    assert noise["hidden"] is True and noise["score"] < HIDE_BELOW
    assert noise["reason"] == "Sport, som du sjelden leser."
    assert data["stories"][0]["published_at"].endswith("Z")
    assert data["ai"] is False
    assert [s["key"] for s in data["sources"]][:2] == ["tu", "kode24"]


def test_feed_marks_failed_sources(client, db):
    db.add(Setting(key="errors", value="reddit"))
    db.commit()
    sources = {s["key"]: s["failed"] for s in client.get("/api/feed").json()["sources"]}
    assert sources["reddit"] is True and sources["nrk"] is False


def test_voting_hides_and_shows(client, db):
    story = add_story(db, "Kjendisnytt")
    response = client.post(f"/api/stories/{story.id}/vote", json={"vote": -1})
    assert response.json() == {"id": story.id, "vote": -1}
    row = client.get("/api/feed").json()["stories"][0]
    assert row["hidden"] is True and row["vote"] == -1

    client.post(f"/api/stories/{story.id}/vote", json={"vote": 0})
    db.refresh(story)
    assert story.vote == 0 and story.voted_at is None


def test_a_vote_moves_similar_stories(client, db):
    liked = add_story(db, "Rust kommer til Linux-kjernen")
    similar = add_story(db, "Rust 2.0 lansert", hours_old=3)
    other = add_story(db, "Været i helgen", hours_old=2)
    client.post(f"/api/stories/{liked.id}/vote", json={"vote": 1})
    scores = {s["id"]: s["score"] for s in client.get("/api/feed").json()["stories"]}
    assert scores[similar.id] > scores[other.id]


def test_vote_is_checked(client, db):
    story = add_story(db)
    assert client.post(f"/api/stories/{story.id}/vote", json={"vote": 5}).status_code == 422
    assert client.post("/api/stories/9999/vote", json={"vote": 1}).status_code == 404


def test_interests_are_saved_and_trigger_rescoring(client, db):
    story = add_story(db, ai_score=40, scored_votes=0)
    assert client.get("/api/interests").json() == {"text": ""}
    client.put("/api/interests", json={"text": "  Romfart og energi  "})
    assert client.get("/api/interests").json() == {"text": "Romfart og energi"}
    db.refresh(story)
    from app import curator
    assert curator.due(db, 0) == [story]


def test_refresh_is_throttled(client, db, monkeypatch):
    monkeypatch.setattr(fetcher, "fetch_all", lambda: ({"nrk": []}, {}))
    first = client.post("/api/refresh")
    assert first.status_code == 200
    assert first.json()["failed"] == []
    assert client.post("/api/refresh").status_code == 429

    db.get(Setting, "refreshed_at").value = (utcnow() - timedelta(hours=1)).isoformat()
    db.commit()
    assert client.post("/api/refresh").status_code == 200


def test_old_stories_are_not_listed(client, db):
    add_story(db, "Gammel", hours_old=24 * 30, vote=1)
    add_story(db, "Ny")
    assert [s["title"] for s in client.get("/api/feed").json()["stories"]] == ["Ny"]
    assert db.query(Story).count() == 2
