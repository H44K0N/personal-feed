# Personal feed

Everything I read in a day on one page: Teknisk Ukeblad, kode24, VG, NRK, r/norge and Ars Technica. Gemini reads each new story and scores how likely I am to want it; stories that score low are folded away. Every story has **Mer som dette** and **Mindre som dette**, and those votes steer what comes next.

It looks like [tischbein.dev](https://tischbein.dev) and [Sjekka](https://sjekka.tischbein.dev): Libron, the dark ink-and-champagne palette, hairline cards, pill buttons.

## How the sorting works

1. **Fetching.** Every 20 minutes (and on the Oppdater button, at most every two minutes) the app reads all six feeds side by side. A feed that fails is struck through in the source list; the others carry on. Stories older than 14 days that nobody voted on are dropped.
2. **Gemini's read.** New stories are sent to Gemini in batches of 40, together with what you wrote under "Hva liker du?" and the last 40 stories you voted up and down. It gives each a score from 0 to 100 and one sentence on why, shown under the title. Once five more votes have come in, stories from the last 36 hours are read again.
3. **Your votes, right away.** Words and sources from stories you vote up lift similar stories; those you vote down sink them. This happens the moment you vote, without waiting for Gemini, and is all there is without a Gemini key.
4. **The order.** "For deg" sorts by score with a small penalty per hour of age, so yesterday's best gives way to today's. "Nyeste" is plain time order. Anything under 35 is folded away behind "Vis skjulte saker".

A second click on a vote takes it back.

## Running it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # add GEMINI_API_KEY (optional)
.venv/bin/uvicorn app.main:app --reload
```

Open http://localhost:8000. `RUN_FETCHER=0` serves the page without fetching.

With Docker: `docker compose up -d --build` serves it on `127.0.0.1:8001`. There is no login, so put it behind something like Cloudflare Access before exposing it.

Settings are in `.env.example`.

## Developing

- `app/sources.py`: the feeds and the RSS/Atom parser. To add a source, add it here and to `SHORT` in `static/feed.js`.
- `app/fetcher.py`: fetch, store new stories by URL, prune, then curate. Runs in a loop in the app's lifespan.
- `app/curator.py`: the Gemini prompt and scoring.
- `app/taste.py`: the instant ranking from votes, and the sort order. Pure functions.
- `app/main.py`: the API (`/api/feed`, `/api/stories/{id}/vote`, `/api/interests`, `/api/refresh`) and the static page.
- `static/`: plain HTML, CSS and JS. No build step.

```bash
.venv/bin/ruff check . && .venv/bin/pytest -q
```

Tests never fetch feeds or call Gemini.

### Note on Reddit

Reddit sometimes answers 403 or 429 to servers in data centres. When it does, r/norge is struck through and the rest of the feed works as normal.
