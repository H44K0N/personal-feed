from datetime import datetime

from app.sources import SOURCES, parse, strip_html

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:vg="http://www.vg.no/namespace" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Test</title>
  <item>
    <title>Rust kommer til Linux</title>
    <link>https://example.com/rust</link>
    <description>&lt;p&gt;Kjernen f\xc3\xa5r &lt;b&gt;mer&lt;/b&gt;   Rust.&lt;/p&gt;&lt;img src="https://img.example.com/a.jpg"&gt;</description>
    <pubDate>Thu, 29 Oct 2026 13:55:16 GMT</pubDate>
  </item>
  <item>
    <title>Kan dette skje i Norge?</title>
    <link>https://www.vg.no/i/64EWvz</link>
    <pubDate>Thu, 29 Oct 2026 14:55:16 +0100</pubDate>
    <vg:img>https://akamai.vgc.no/v2/images/x.jpg</vg:img>
  </item>
  <item>
    <title>Tyrifjorden blir drikkevann</title>
    <link>https://example.com/tyri</link>
    <description>Tyrifjorden blir drikkevann.</description>
    <pubDate>Thu, 29 Oct 2026 04:00:00 GMT</pubDate>
    <media:content url="https://img.example.com/media.jpg" medium="image"/>
  </item>
  <item><title>Kryssord og spill</title><link>https://example.com/kryssord</link></item>
  <item><title></title><link>https://example.com/empty</link><pubDate>Thu, 29 Oct 2026 04:00:00 GMT</pubDate></item>
  <item><title>Ingen lenke</title><link>javascript:alert(1)</link><pubDate>Thu, 29 Oct 2026 04:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <title>r/norge</title>
  <entry>
    <title>Hvorfor er str\xc3\xb8mmen s\xc3\xa5 dyr?</title>
    <link href="https://www.reddit.com/r/norge/comments/abc/hvorfor/"/>
    <published>2026-10-28T16:02:27+00:00</published>
    <content type="html">&lt;div&gt;&lt;p&gt;Lurer p\xc3\xa5 dette.&lt;/p&gt;&lt;/div&gt; submitted by &lt;a href="https://www.reddit.com/user/x"&gt; /u/someone &lt;/a&gt; &lt;br/&gt; &lt;a href="x"&gt;[link]&lt;/a&gt; &lt;a href="y"&gt;[comments]&lt;/a&gt;</content>
    <media:thumbnail url="https://b.thumbs.redditmedia.com/t.jpg"/>
  </entry>
  <entry>
    <title>Uten dato</title>
    <link href="https://www.reddit.com/r/norge/comments/def/"/>
  </entry>
</feed>"""


def test_reads_rss_items():
    items = parse(RSS)
    assert [i.title for i in items] == ["Rust kommer til Linux", "Kan dette skje i Norge?", "Tyrifjorden blir drikkevann"]
    rust, vg, tyri = items
    assert rust.url == "https://example.com/rust"
    assert rust.summary == "Kjernen får mer Rust."
    assert rust.image == "https://img.example.com/a.jpg"
    assert rust.published_at == datetime(2026, 10, 29, 13, 55, 16)
    # dates become naive UTC
    assert vg.published_at == datetime(2026, 10, 29, 13, 55, 16)
    assert vg.image == "https://akamai.vgc.no/v2/images/x.jpg"
    # a summary that only repeats the title is dropped
    assert tyri.summary == ""
    assert tyri.image == "https://img.example.com/media.jpg"


def test_skips_undated_untitled_and_non_web_items():
    urls = [i.url for i in parse(RSS)]
    assert "https://example.com/kryssord" not in urls
    assert "https://example.com/empty" not in urls
    assert not any(u.startswith("javascript:") for u in urls)


def test_reads_atom_and_drops_reddit_footer():
    items = parse(ATOM)
    assert len(items) == 1
    post = items[0]
    assert post.title == "Hvorfor er strømmen så dyr?"
    assert post.url == "https://www.reddit.com/r/norge/comments/abc/hvorfor/"
    assert post.summary == "Lurer på dette."
    assert post.image == "https://b.thumbs.redditmedia.com/t.jpg"
    assert post.published_at == datetime(2026, 10, 28, 16, 2, 27)


def test_long_summaries_are_shortened_at_a_word():
    body = "ord " * 300
    xml = f"""<rss><channel><item><title>T</title><link>https://e.com/t</link>
    <description>{body}</description><pubDate>Thu, 29 Oct 2026 04:00:00 GMT</pubDate></item></channel></rss>"""
    summary = parse(xml.encode())[0].summary
    assert len(summary) <= 402
    assert summary.endswith("ord …")


def test_strip_html():
    assert strip_html("<p>a <i>b</i>\n\n c</p>") == ("a b c", None)


def test_sources_match_the_page():
    """static/feed.js names every source by key."""
    with open("static/feed.js", encoding="utf-8") as script:
        text = script.read()
    for source in SOURCES:
        assert f"{source.key}:" in text
