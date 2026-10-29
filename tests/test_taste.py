from datetime import datetime, timedelta
from types import SimpleNamespace

from app import taste


def story(title, vote=0, source="nrk", summary="", ai_score=None):
    return SimpleNamespace(title=title, summary=summary, source=source, vote=vote, ai_score=ai_score)


def test_no_votes_is_neutral():
    learned = taste.learn([])
    assert taste.score(story("Hva som helst"), learned) == taste.NEUTRAL


def test_liked_words_lift_and_disliked_words_sink():
    learned = taste.learn([
        story("Rust i Linux-kjernen", vote=1),
        story("Ny Rust-kompilator", vote=1),
        story("Fotball: Rosenborg tapte", vote=-1),
        story("Fotball: Brann vant", vote=-1),
    ])
    rust = taste.score(story("Rust 2.0 er ute"), learned)
    football = taste.score(story("Fotball i kveld"), learned)
    other = taste.score(story("Været blir fint"), learned)
    assert rust > other > football


def test_sources_count_too():
    learned = taste.learn([story(f"Sak {i}", vote=-1, source="vg") for i in range(5)])
    assert taste.score(story("Noe helt annet", source="vg"), learned) < taste.NEUTRAL
    assert taste.score(story("Noe helt annet", source="ars"), learned) == taste.NEUTRAL


def test_gemini_score_is_the_base():
    learned = taste.learn([])
    assert taste.score(story("Sak", ai_score=82), learned) == 82


def test_a_vote_on_the_story_settles_it():
    learned = taste.learn([])
    assert taste.score(story("Sak", vote=1, ai_score=5), learned) == 100
    assert taste.score(story("Sak", vote=-1, ai_score=95), learned) == 0


def test_score_stays_in_range():
    learned = taste.learn([story("rust rust kompilator linux kjerne", vote=1)] * 20)
    assert taste.score(story("rust kompilator linux kjerne", ai_score=99), learned) == 100


def test_stopwords_are_ignored():
    assert taste.words("Det er en sak om Rust og the Linux") == {"sak", "rust", "linux"}


def test_newer_stories_rank_higher_at_the_same_score():
    now = datetime(2026, 10, 29, 12)
    assert taste.rank(60, now - timedelta(hours=1), now) > taste.rank(60, now - timedelta(hours=10), now)
    # a much better story outranks a slightly newer one
    assert taste.rank(90, now - timedelta(hours=5), now) > taste.rank(50, now, now)
