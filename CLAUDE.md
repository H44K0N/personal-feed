# Personal feed

One reader's news feed: RSS/Atom from TU, kode24, VG, NRK, r/norge and Ars Technica, scored by Gemini against the reader's votes and interests. The README covers how sorting works and how to run it.

## Commands

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q
RUN_FETCHER=0 uvicorn app.main:app   # page without fetching
```

## Rules

- **Tests never fetch feeds or call Gemini.** Fake `fetcher.fetch`/`fetcher.fetch_all` and `curator.ask` (set `curator.client` to anything not None).
- **Every change gets tests.** Prefer checking that a new test fails when the code is broken on purpose.
- **Keep `SOURCES` in `app/sources.py` and `SHORT` in `static/feed.js` in step.** A test checks it.
- **Votes are the taste.** Voted stories are never pruned.
- **Timestamps are naive UTC** via `models.utcnow()`.
- **User-facing text is Norwegian (bokmål).** Code, comments and commits are English.
- **Design mirrors tischbein.dev and Sjekka:** Libron everywhere (no second font), the colour tokens in `style.css`, hairline cards, pill buttons. No gradients, no emoji, no decorative fluff. Build DOM with `textContent`, never `innerHTML` with data.
- **One app process only.** The fetch loop runs inside it.
- **Schema changes:** `create_all` only creates missing tables. A new column on an existing table needs a migration.
