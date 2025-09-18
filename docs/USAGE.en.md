# Usage Guide

This guide covers installation, CLI usage, options, and tips to build EPUB books from shamela.ws with Kindle and Apple Books compatibility.

## Install

- Virtualenv (recommended):
  - `python -m venv .venv && source .venv/bin/activate`
- Editable install for development:
  - `pip install -e .[dev]`

## Run CLI

- As module:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8`
- As console script:
  - `shamela-to-epub 'https://shamela.ws/book/<id>' [options]`

Output EPUB is written to `output/` by default.

## Options

- `-o, --output <PATH>`: output EPUB path.
- `--throttle <sec>`: polite delay between requests (use 0.6–1.0).
- `--limit <N>`: limit number of chapters (debug).
- `--profile minimal|kindle|apple`: sanitizer/semantics profile.
- `--no-cache`: disable local cache for HTML/images.
- Cover:
  - `--cover-auto`: auto-search (Google/DuckDuckGo/Bing; HTML only, no JS) with size/type/aspect filters.
  - `--cover <file>`: local cover (JPEG/PNG).
  - `--cover-min-size WxH`, `--cover-min-bytes <B>`, `--cover-convert-jpeg`.
- Parallelism:
  - `--workers <1..4>`: worker threads.
  - `--jitter <0..1>`: throttle jitter fraction.

## Kindle vs Apple Books

- Kindle (Send‑to‑Kindle):
  - Minimal EPUB profile, no embedded fonts, no separate cover page.
  - nav.xhtml present in manifest, not added to spine.
  - Endnotes: global numbering; `endnotes.xhtml` with back links.
  - Prefer JPEG covers; heavy fonts/cover pages can cause e999.

- Apple Books:
  - Strict XML validation. Wherever `epub:type` is used, root `<html>` declares `xmlns:epub`.
  - Chapter content is sanitized (profile `apple`), tags balanced and limited to a safe set.
  - Inline images (JPEG/PNG) are embedded and `src` rewritten.

## Examples

- Basic:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8`
- Auto cover:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8 --cover-auto`
- Local cover + convert to JPEG:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --cover ./cover.heic --cover-convert-jpeg`

## Nested TOC and Endnotes
- Headings `h2/h3` inside chapters receive stable IDs and appear as nested items in `nav.xhtml`.
- Endnotes: global numbering; backlinks include a reference to the nearest section within the chapter.

## Cache
- Local cache in `.cache/shamela_books/` (override via `SHAMELA_CACHE_DIR`).
- Disable with `--no-cache` or in API `use_cache=False`.
