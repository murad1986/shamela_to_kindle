shamela_books — Shamela.ws to EPUB (RTL)

Minimal, Kindle‑friendly EPUB builder for books from `shamela.ws`. Focus: clean Arabic text (RTL), simple structure, and Send‑to‑Kindle compatibility.

## TL;DR
- Basic: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- With cover: add `--cover-auto` (or `--cover path/to.jpg|png`)
- Output: `output/<Title> - <Publisher>.epub`

## Repository Layout
- `src/shamela_books/`: library modules (parsers, builder, CLI).
- `output/`: generated files (ignored by git).
- `docs/`: detailed docs (usage, endnotes, Apple Books, development).

## Supported Format (one profile)
- EPUB, minimal profile:
  - No embedded fonts.
  - No cover or “بطاقة الكتاب” info page.
  - `nav.xhtml` present in manifest, not added to spine.
  - Clean RTL XHTML chapters with external CSS only.

## Usage
- Full book: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- With cover (Google Images): add `--cover-auto` or `--cover path/to.jpg|png`
- Quick test (first N chapters): `--limit N`
- Output file name: `<Title> - <Publisher>.epub`
  - Arabic preserved, spaces intact, no underscores.
  - Leading “كتاب/الكتاب” is removed from the title.

## Options
- `-o, --output`: custom output path.
- `--throttle <seconds>`: delay between requests (default 0.8). Use 0.6–1.0 for polite crawling.
- `--limit <N>`: fetch first N chapters (debugging).
- `--cover-auto`: try to fetch first Google Images result as cover; falls back to no cover if not found.
- `--cover path/to.jpg|png`: provide a local cover (recommended ≥ 300×300).

### Options Summary

| Option | Description | Default | Example |
|---|---|---|---|
| `-o, --output <path>` | Output file path | `output/<Title> - <Publisher>.epub` | `-o output/book.epub` |
| `--throttle <sec>` | Delay between HTTP requests | `0.8` | `--throttle 0.6` |
| `--limit <N>` | Fetch only first N chapters (quick test) | all chapters | `--limit 10` |
| `--cover-auto` | Auto‑search cover (Google Images + size/type filters) | off | `--cover-auto` |
| `--cover <file>` | Local cover (JPEG/PNG, ≥ 300×300) | none | `--cover cover.jpg` |

## What Works / What Doesn’t
- Works reliably: Minimal EPUB (above) — passes Send‑to‑Kindle for this book.
- Not reliable for Send‑to‑Kindle (kept out by design):
  - EPUB with embedded fonts and/or extra pages (cover/info) — often e999.
  - Legacy profiles (NCX/complex metadata) — inconsistent.

More details about the profile and cover logic: see TECHNICAL.md.

## As a Library
```python
from shamela_books import build_epub_from_url

out = build_epub_from_url(
    'https://shamela.ws/book/158',
    throttle=0.8,
    cover_auto=True,
    cover_query='...',
    cover_min_size=(600, 800),
)
print('EPUB at', out)
```

## Notes
- Respect the website. Throttle requests and avoid parallel scraping.
- Resulting chapters are right‑to‑left; rendering depends on your reader.
- If Kindle still rejects, try USB copy to device (no server conversion).

## Docs
- Usage: `docs/USAGE.en.md`
- Endnotes: `docs/ENDNOTES.en.md`
- Apple Books: `docs/APPLE_BOOKS.en.md`
- Development: `docs/DEVELOPMENT.en.md`
- Troubleshooting: `docs/TROUBLESHOOTING.en.md`
