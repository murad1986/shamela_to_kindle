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
- Cover:
  - `--cover-auto`: auto-search (Google/DuckDuckGo/Bing; HTML only, no JS) with filters.
  - `--cover <file>`: local cover (JPEG/PNG/HEIC — needs Pillow/pillow-heif).
  - `--cover-min-size WxH`: minimal cover size.
  - `--cover-min-bytes <B>`: minimal file size.
  - `--cover-convert-jpeg`: convert PNG/HEIC to JPEG (Kindle friendly).
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
  - Chapter content is sanitized: source `<span>/<a>` wrappers removed, tags are balanced.
  - Allowlist sanitizer prevents tag mismatch errors.

## Examples

- Basic:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8`
- Auto cover:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8 --cover-auto`
- Local cover + convert to JPEG:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --cover ./cover.heic --cover-convert-jpeg`

