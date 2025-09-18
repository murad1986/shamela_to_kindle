# Troubleshooting

## Apple Books: “Namespace prefix epub … not defined”
- Reason: `epub:type` is used but `xmlns:epub` is missing.
- Fix: already implemented — root `<html>` declares `xmlns:epub` on all such pages.

## Apple Books: “Opening and ending tag mismatch: span … and p”
- Reason: broken/nested `<span>`/`<a>` wrappers from the source.
- Fix: chapter content is sanitized — source `<span>`/`<a>` removed; tags balanced; allowlist sanitizer applied.
- Tip: remove the previous import from Books before re‑import (cache).

## Kindle: e999 when uploading
- Causes: embedded fonts, heavy covers, dedicated cover page, non‑minimal profiles.
- Fix: minimal/kindle profile, no cover page, prefer JPEG, `nav.xhtml` in manifest but not in `spine`. If still e999, transfer via USB.

## Cover not added
- Might fail MIME/size/bytes/aspect checks or due to network.
- Try `--cover <file>` or adjust `--cover-query`; for PNG add `--cover-convert-jpeg`.

## Stale/old content
- Disable cache with `--no-cache` and re‑run, or remove `.cache/shamela_books/`.

## Network/Timeouts
- Increase `--throttle` and reduce `--workers`.
- Retry; polite rate limiter with jitter is enabled.

## Endnote numbering
- In text — always global `1..N` for consistency and reliable linking.
- End page — `<ol>` renders the number; explicit `G.` prefix is omitted to avoid “G.G”.
