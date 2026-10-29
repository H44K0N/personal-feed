from datetime import timedelta

from app.models import Story, utcnow


def add_story(db, title="En sak", source="nrk", hours_old=1, summary="", **fields) -> Story:
    story = Story(
        source=source,
        url=f"https://example.com/{source}/{title.replace(' ', '-')}/{hours_old}",
        title=title,
        summary=summary,
        published_at=utcnow() - timedelta(hours=hours_old),
        **fields,
    )
    db.add(story)
    db.commit()
    return story
