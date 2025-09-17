shamela_books — Shamela.ws to EPUB (RTL)

Minimal, Kindle‑friendly EPUB3 builder for books from `shamela.ws`. Focus: clean Arabic text (RTL), simple structure, and Send‑to‑Kindle compatibility.

## Repository Layout
- `scripts/shamela_to_epub.py`: main script (no external deps).
- `output/`: generated files (ignored by git).

## Supported Format (one profile)
- EPUB3, minimal profile:
  - No embedded fonts.
  - No cover or “بطاقة الكتاب” info page.
  - `nav.xhtml` present in manifest, not added to spine.
  - Clean RTL XHTML chapters with external CSS only.

## Usage
- Full book: `python3 scripts/shamela_to_epub.py 'https://shamela.ws/book/158' --throttle 0.6`
- Quick test (first N chapters): `--limit N`
- Output file name: `<Title> - <Publisher>.epub`
  - Arabic preserved, spaces intact, no underscores.
  - Leading “كتاب/الكتاب” is removed from the title.

## Options
- `-o, --output`: custom output path.
- `--throttle <seconds>`: delay between requests (default 0.8). Use 0.6–1.0 for polite crawling.
- `--limit <N>`: fetch first N chapters (debugging).

## What Works / What Doesn’t
- Works reliably: Minimal EPUB3 (above) — passes Send‑to‑Kindle for this book.
- Not reliable for Send‑to‑Kindle (kept out by design):
  - EPUB3 with embedded fonts and/or extra pages (cover/info) — often e999.
  - EPUB2 (OPF 2.0 + NCX) — inconsistent, e999.
  - DOCX — not accepted in our tests for this title.

## Notes
- Respect the website. Throttle requests and avoid parallel scraping.
- Resulting chapters are right‑to‑left; rendering depends on your reader.
- If Kindle still rejects, try USB copy to device (no server conversion).

