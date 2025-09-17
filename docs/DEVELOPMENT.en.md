# Development

## Project structure

- `src/shamela_books/` — library (API, parsers, EPUB builder, CLI):
  - `api.py` — high‑level `build_epub_from_url(...)`.
  - `parsers.py` — TOC/meta/content parser + sanitizer.
  - `endnotes.py` — extract/link/build endnotes.
  - `builder.py` — XHTML/OPF/ZIP generation.
  - `cover.py` — cover fetch/validation/conversion.
  - `http.py` — `fetch`, `RateLimiter`.
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

## Commits & PRs

- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:` …)
- Call out Kindle vs Apple Books constraints explicitly.

## Security

- No secrets in repo. Data in `data/` (gitignored).
- HTML parsing only; no JS eval. Rate‑limited network access.

