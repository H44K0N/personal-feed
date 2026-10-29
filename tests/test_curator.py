import pytest

from app import curator
from app.curator import Verdict, Verdicts
from app.models import Setting
from tests.helpers import add_story


@pytest.fixture
def gemini(monkeypatch):
    """A fake Gemini that scores every story 70 and remembers the prompts."""
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        ids = [int(part.split(",")[0]) for part in prompt.split('{"id": ')[1:]]
        return Verdicts(stories=[Verdict(id=i, score=70, reason="Om noe du liker.") for i in ids])

    monkeypatch.setattr(curator, "client", object())
    monkeypatch.setattr(curator, "ask", ask)
    return prompts


def test_without_a_key_nothing_is_scored(db):
    add_story(db)
    assert curator.client is None
    assert curator.curate(db) == 0


def test_scores_new_stories(db, gemini):
    story = add_story(db, "Rust i kjernen")
    assert curator.curate(db) == 1
    db.refresh(story)
    assert story.ai_score == 70
    assert story.ai_reason == "Om noe du liker."
    assert story.scored_votes == 0
    # nothing left to do
    assert curator.curate(db) == 0
    assert len(gemini) == 1


def test_prompt_carries_votes_and_interests(db, gemini):
    add_story(db, "Rust i kjernen", vote=1)
    add_story(db, "Kjendis gifter seg", vote=-1, source="vg")
    db.add(Setting(key="interests", value="Programmering og romfart"))
    db.commit()
    add_story(db, "Ny rakett", source="ars")
    curator.curate(db)
    prompt = gemini[0]
    assert "Programmering og romfart" in prompt
    liked, disliked = prompt.split("## Stories they asked for less of")
    assert "[NRK] Rust i kjernen" in liked
    assert "[VG] Kjendis gifter seg" in disliked
    # voted stories are examples, not scored again
    assert '"title": "Ny rakett"' in prompt
    assert '"title": "Rust i kjernen"' not in prompt


def test_unknown_ids_are_ignored(db, monkeypatch):
    story = add_story(db)
    monkeypatch.setattr(curator, "client", object())
    monkeypatch.setattr(curator, "ask", lambda prompt: Verdicts(stories=[Verdict(id=999, score=1, reason="x")]))
    assert curator.curate(db) == 0
    db.refresh(story)
    assert story.ai_score is None


def test_a_failing_batch_does_not_stop_the_rest(db, monkeypatch):
    for i in range(curator.BATCH + 1):
        add_story(db, f"Sak {i}", hours_old=i + 1)
    calls = []

    def ask(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            raise RuntimeError("503")
        ids = [int(part.split(",")[0]) for part in prompt.split('{"id": ')[1:]]
        return Verdicts(stories=[Verdict(id=i, score=50, reason="ok") for i in ids])

    monkeypatch.setattr(curator, "client", object())
    monkeypatch.setattr(curator, "ask", ask)
    assert curator.curate(db) == 1
    assert len(calls) == 2


def test_recent_stories_are_scored_again_once_the_taste_moves(db, gemini):
    fresh = add_story(db, "Fersk", hours_old=2, ai_score=40, ai_reason="x", scored_votes=0)
    old = add_story(db, "Gammel", hours_old=curator.RESCORE_HOURS + 5, ai_score=40, ai_reason="x", scored_votes=0)
    for i in range(curator.RESCORE_AFTER_VOTES - 1):
        add_story(db, f"Stemt {i}", vote=1)
    assert curator.due(db, curator.vote_count(db)) == []
    add_story(db, "En til", vote=1)
    assert curator.due(db, curator.vote_count(db)) == [fresh]
    curator.curate(db)
    db.refresh(fresh)
    db.refresh(old)
    assert fresh.ai_score == 70
    assert old.ai_score == 40
