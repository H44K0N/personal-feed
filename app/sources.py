"""The feeds, and reading RSS 2.0 and Atom into plain items."""

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
import xml.etree.ElementTree as ET



@dataclass(frozen=True)
class Source:
    key: str
    name: str
    url: str


# Keep in step with SOURCES in static/feed.js (names and order shown).
SOURCES = [
    Source("tu", "Teknisk Ukeblad", "https://www.tu.no/rss"),
    Source("kode24", "kode24", "https://rss.kode24.no/"),
    Source("vg", "VG", "https://www.vg.no/rss/feed"),
    Source("nrk", "NRK", "https://www.nrk.no/toppsaker.rss"),
    Source("reddit", "r/norge", "https://www.reddit.com/r/norge/.rss"),
    Source("ars", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
]
BY_KEY = {source.key: source for source in SOURCES}

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
VG = "{http://www.vg.no/namespace}"

SUMMARY_CHARS = 400


@dataclass
class Item:
    url: str
    title: str
    summary: str
    image: str | None
    published_at: datetime


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.image = None

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == "img" and self.image is None:
            self.image = dict(attrs).get("src")


def strip_html(html: str) -> tuple[str, str | None]:
    """The text of an HTML snippet, whitespace collapsed, and its first image."""
    parser = _Text()
    parser.feed(html or "")
    text = re.sub(r"\s+", " ", "".join(parser.parts)).strip()
    return text, parser.image


def _shorten(text: str) -> str:
    if len(text) <= SUMMARY_CHARS:
        return text
    return text[:SUMMARY_CHARS].rsplit(" ", 1)[0] + " …"


def _same(a: str, b: str) -> bool:
    """Whether a summary just repeats the title (TU's often do)."""
    return a.rstrip(" .").casefold() == b.rstrip(" .").casefold()


def _date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def _text(element, path) -> str:
    found = element.find(path)
    return (found.text or "").strip() if found is not None else ""


def _media_image(element) -> str | None:
    for path in (f"{MEDIA}thumbnail", f"{MEDIA}content", f"{VG}img"):
        found = element.find(path)
        if found is None:
            continue
        url = found.get("url") or (found.text or "").strip()
        if url:
            return url
    group = element.find(f"{MEDIA}group")
    if group is not None:
        return _media_image(group)
    for enclosure in element.findall("enclosure"):
        if (enclosure.get("type") or "image").startswith("image") and enclosure.get("url"):
            return enclosure.get("url")
    return None


def _http(url: str | None) -> str | None:
    return url if url and url.startswith(("https://", "http://")) else None


def parse(xml: bytes) -> list[Item]:
    """Items from an RSS 2.0 or Atom document. Items without a title, a web
    link or a date are skipped: undated ones are evergreen pages (TU's
    crossword and lunch menu), not news."""
    root = ET.fromstring(xml)
    items = []
    if root.tag == f"{ATOM}feed":
        for entry in root.findall(f"{ATOM}entry"):
            link = None
            for candidate in entry.findall(f"{ATOM}link"):
                if candidate.get("rel", "alternate") == "alternate":
                    link = candidate.get("href")
                    break
            html = _text(entry, f"{ATOM}content") or _text(entry, f"{ATOM}summary")
            summary, inline_image = strip_html(html)
            items.append((
                link,
                _text(entry, f"{ATOM}title"),
                summary,
                _media_image(entry) or inline_image,
                _date(_text(entry, f"{ATOM}published") or _text(entry, f"{ATOM}updated")),
            ))
    else:
        for entry in root.iter("item"):
            html = _text(entry, "description") or _text(entry, f"{CONTENT}encoded")
            summary, inline_image = strip_html(html)
            items.append((
                _text(entry, "link") or _text(entry, "guid"),
                _text(entry, "title"),
                summary,
                _media_image(entry) or inline_image,
                _date(_text(entry, "pubDate") or _text(entry, "{http://purl.org/dc/elements/1.1/}date")),
            ))

    result = []
    for link, title, summary, image, published in items:
        title = strip_html(title)[0]
        if not title or not _http(link) or published is None:
            continue
        # Reddit's summary is "submitted by /u/x [link] [comments]" at the end
        summary = re.sub(r"\s*submitted by /u/\S+.*$", "", summary)
        result.append(Item(
            url=link.strip(),
            title=title[:500],
            summary=_shorten("" if _same(summary, title) else summary),
            image=_http(image),
            published_at=published,
        ))
    return result
