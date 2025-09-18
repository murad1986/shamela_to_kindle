# Development

## Project structure

- `src/shamela_books/` — library (API, parsers, EPUB builder, CLI):
  - `api.py` — high‑level `build_epub_from_url(...)`.
  - `parsers.py` — TOC/meta/content parser + sanitizer.
  - `endnotes.py` — extract/link/build endnotes.
  - `builder.py` — XHTML/OPF/ZIP generation.
  - `cover.py` — cover fetch/validation/conversion.
- `http.py` — `fetch`, `RateLimiter`.
  - `providers.py` — provider protocol and default `ShamelaProvider`.
  - `sanitizer.py` — profile‑based sanitizer (bleach if available).
  - `cache.py` — simple byte cache (HTML/images/covers).
  - `cli.py` — thin CLI on top of API.

## Bootstrap

- Env:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
- Lint/format:
  - `ruff check src tests`
  - `black src tests`
- Tests:
  - `pytest -q`

## Public API

- `build_epub_from_url(url, *, profile='minimal', use_cache=True, on_event=None, provider=None, ...) -> str`
- `fetch_toc(url, *, provider=None) -> list[(id, title, url)]`
- `fetch_chapter(book_url, chapter_url, *, provider=None) -> str`
- Provider protocol: `Provider.fetch_index(url, use_cache) -> str`, `Provider.fetch_chapter(url, referer, use_cache) -> str`
- Progress callback: `on_event(ev: dict)`; events like `chapter_fetch_start`/`chapter_fetch_done` with `index` and `id`.
- Exceptions: `ShamelaError`.

## Implementation notes

- Chapters are sanitized via profile‑based sanitizer; inline images are embedded and `src` rewritten.
- Nested TOC is derived from `h2/h3` inside chapter content; IDs are stable (`sec-<chapterId>-<n>`).
- Endnotes are globally numbered and rendered on `endnotes.xhtml`, with backlinks to chapter and nearest section.
- EPUB: `nav.xhtml` present; landmarks nav included; spine keeps nav out for Kindle friendliness.

## Commits & PRs

- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:` …)
- Call out Kindle vs Apple Books constraints explicitly.

## Security

- No secrets in repo. Data in `data/` (gitignored).
- HTML parsing only; no JS eval. Rate‑limited network access.
