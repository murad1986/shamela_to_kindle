shamela_books — Shamela.ws to EPUB (RTL)

Minimal, Kindle/Apple‑friendly EPUB builder for books from `shamela.ws`. Focus: clean Arabic text (RTL), simple structure, nested TOC, inline images, and Send‑to‑Kindle compatibility.

## TL;DR
- Basic: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- Cover: add `--cover-auto` or `--cover path/to.jpg|png`
- Profiles: `--profile minimal|kindle|apple`
- Cache off: `--no-cache`
- Output default: `output/<Title> - <Publisher>.epub`

## Repository Layout
- `src/shamela_books/`: library modules (parsers, builder, CLI).
- `output/`: generated files (ignored by git).
- `docs/`: detailed docs (usage, endnotes, Apple Books, development).

## Supported Profiles
- Minimal (default): clean RTL XHTML, landmarks, nested TOC (h2/h3), inline images, endnotes page.
- Kindle: same as minimal with sanitizer tuned for Kindle acceptance.
- Apple: stricter sanitizer to avoid XML issues; explicit `xmlns:epub` when `epub:type` is used.

## Usage
- Full book: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- With cover: `--cover-auto` or `--cover path/to.jpg|png`
- Quick test (first N chapters): `--limit N`
- Profile: `--profile apple` for Apple Books; `--profile kindle` for Send‑to‑Kindle.
- Output file name: `<Title> - <Publisher>.epub` (Arabic preserved; strips leading “كتاب/الكتاب”).

## Options
- `-o, --output`: custom output path.
- `--throttle <sec>`: delay between requests (default 0.8). Use 0.6–1.0 for polite crawling.
- `--limit <N>`: fetch first N chapters (debug).
- `--profile minimal|kindle|apple`: sanitizer/semantics profile.
- `--no-cache`: disable local cache for HTML and images.
- Cover:
  - `--cover-auto`: auto‑search (Google/DuckDuckGo/Bing) with size/type/aspect filters.
  - `--cover <file>`: local cover (JPEG/PNG).
  - `--cover-min-size WxH` / `--cover-min-bytes B` / `--cover-convert-jpeg`.
- Parallelism:
  - `--workers 1..4`, `--jitter 0..1`.

### Options Summary

| Option | Description | Default | Example |
|---|---|---|---|
| `-o, --output <path>` | Output EPUB path | `output/<Title> - <Publisher>.epub` | `-o output/book.epub` |
| `--throttle <sec>` | Delay between requests | `0.8` | `--throttle 0.6` |
| `--limit <N>` | Fetch first N chapters | all | `--limit 10` |
| `--profile <p>` | Sanitizer profile | `minimal` | `--profile apple` |
| `--no-cache` | Disable local cache | off | `--no-cache` |
| `--cover-auto` | Auto cover search | off | `--cover-auto` |
| `--cover <file>` | Local cover file | none | `--cover cover.jpg` |
| `--workers <n>` | Parallel workers | `2` | `--workers 2` |
| `--jitter <f>` | Throttle jitter 0..1 | `0.3` | `--jitter 0.1` |

## What Works / What Doesn’t
- Works: minimal/kindle/apple profiles, nested TOC (h2/h3), inline images (JPEG/PNG), global endnotes with backlinks.
- May fail with aggressive settings: heavy fonts, unconventional covers, or malformed HTML from source.

More details about the profile and cover logic: see TECHNICAL.md.

## As a Library
```python
from shamela_books import build_epub_from_url, fetch_toc, Provider, ShamelaProvider

def on_event(ev: dict) -> None:
    if ev.get('type') == 'chapter_fetch_start':
        print('start', ev.get('index'), ev.get('id'))

out = build_epub_from_url(
    'https://shamela.ws/book/158',
    throttle=0.8,
    profile='kindle',
    cover_auto=True,
    cover_min_size=(600, 800),
    on_event=on_event,
)
print('EPUB at', out)
```

Provider interface (for future sources): see `src/shamela_books/providers.py` and docs/DEVELOPMENT.en.md.

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
- Technical details: `TECHNICAL.md`
