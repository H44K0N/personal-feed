"""What the votes say, without asking Gemini: words and sources that show up
in stories voted up count for a story, those in stories voted down count
against it. It reacts the moment a vote is cast; Gemini's read follows on the
next refresh. Pure functions, so the ranking is easy to test."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import math
import re

# Words too common to say anything about taste (Norwegian and English)
STOPWORDS = set("""
og i på er det som en et til av for med at har de den ikke om var vil kan
seg han hun men så fra ble blir etter nå skal også mot ut hva når hvor
alle sin sine sitt sier være vært får før over under nye ny nytt dette
the and for with that this from are was has have its into will can new
not but you your our out how why what who about after over more than
""".split())

WORD = re.compile(r"[a-zæøå0-9][a-zæøå0-9+#.-]{2,}", re.IGNORECASE)

# Points a fully liked word or source adds to a 0-100 score
WORD_WEIGHT = 18
SOURCE_WEIGHT = 8
# Score when Gemini has not read a story (no key, or not yet)
NEUTRAL = 50
# Points lost per hour of age when sorting "for deg"
DECAY_PER_HOUR = 1.2


def words(text: str) -> set[str]:
    return {w.strip(".-").lower() for w in WORD.findall(text or "")} - STOPWORDS


@dataclass
class Taste:
    words: dict[str, float]
    sources: dict[str, float]

    def adjust(self, title: str, summary: str, source: str) -> float:
        """Points to add to a story's score, about -26 to +26."""
        found = [self.words[w] for w in words(f"{title} {summary}") if w in self.words]
        word_part = 0.0
        if found:
            # The strongest few signals, so a long summary doesn't drown them
            found.sort(key=abs, reverse=True)
            word_part = math.tanh(sum(found[:4]) / 2)
        return WORD_WEIGHT * word_part + SOURCE_WEIGHT * self.sources.get(source, 0.0)


def learn(voted) -> Taste:
    """A taste from voted stories (anything with title, summary, source, vote)."""
    word_votes: Counter = Counter()
    word_seen: Counter = Counter()
    source_votes: Counter = Counter()
    source_seen: Counter = Counter()
    for story in voted:
        if not story.vote:
            continue
        for w in words(f"{story.title} {story.summary}"):
            word_votes[w] += story.vote
            word_seen[w] += 1
        source_votes[story.source] += story.vote
        source_seen[story.source] += 1
    return Taste(
        # Shrunk towards zero until a word has been seen a few times
        words={w: word_votes[w] / (word_seen[w] + 1) for w in word_votes if word_votes[w]},
        sources={s: source_votes[s] / (source_seen[s] + 2) for s in source_votes},
    )


def score(story, taste: Taste) -> int:
    """The story's score, 0-100: Gemini's read (or neutral) moved by the votes.
    A vote on the story itself settles it."""
    if story.vote > 0:
        return 100
    if story.vote < 0:
        return 0
    base = story.ai_score if story.ai_score is not None else NEUTRAL
    value = base + taste.adjust(story.title, story.summary, story.source)
    return round(min(100, max(0, value)))


def rank(score_value: int, published_at: datetime, now: datetime) -> float:
    """Sort key for "for deg": good stories first, but yesterday's best gives
    way to today's."""
    hours = max(0.0, (now - published_at).total_seconds() / 3600)
    return score_value - DECAY_PER_HOUR * hours
