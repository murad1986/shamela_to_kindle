# Roadmap: EPUB builder improvements (step-by-step, TDD-first)

This document outlines changes to be developed in a separate branch, with a TDD-first approach, small PRs, and easy rollback.

## Goals (in user terms)
- Cleaner content: remove UI cruft (icons/buttons), keep footnotes/anchors.
- Polite parallelism: 2–4 workers, jittered throttling, global domain rate limit.
- Cover improvements: `--cover-query`, `--cover-min-size`, fallback to DuckDuckGo/Bing, optional PNG→JPEG for Kindle.
- Metadata: strict Unicode normalization; no HTML leakage into `dc:title/creator`.
- UX: compact progress bar and summary (chapters, retries, skips).
- Packaging: `pyproject.toml` + console entrypoint (`shamela-to-epub`).
- Quality: ruff/black, pre-commit; basic tests for parsers (TOC/metadata) with fixtures only (no network).
- CI: GitHub Actions for lint/build (no network calls).
- Headers: explicit `User-Agent`, randomized delays (bounded).

## Phasing (small, revertible steps)
1) Tests & fixtures (TDD)
   - Add fixtures: `tests/fixtures/book_index.html`, `tests/fixtures/chapter.html`.
   - Tests: TOC extraction, metadata extraction (title/author), content cleaning unit tests.
   - Decide test runner: `pytest`.

2) Content cleaning
   - Remove empty icon spans (`span.fa`, `i.fa`, known classes), buttons/controls.
   - Keep anchors (`<a id=...>`/`<span id=... class=anchor>`), footnotes and `sup`.
   - Acceptance: tests assert DOM after cleaning contains text but not UI cruft.

3) Metadata hardening
   - Strict scope to the “بطاقة الكتاب” block; Unicode NFKC; strip bidi controls/tatweel.
   - Guard against HTML leakage; tests verifying clean `dc:title/creator`.

4) Parallel polite fetch
   - `ThreadPoolExecutor(max_workers=4)`; global rate limiter + jitter (±30%).
   - Respect `--throttle`; cap to 2 requests/sec domain-wide.
   - Retries with exponential backoff; summary of retries/skips.

5) Progress & summary
   - Single-line compact progress (e.g., `[ 23/100 ] id=... ok/retry`), final report.

6) Cover enhancements
   - `--cover-query` string to override queries.
   - `--cover-min-size WxH` and `--cover-min-bytes`.
   - Fallback providers: DuckDuckGo Images, Bing Images (HTML only, no API keys).
   - Optional PNG→JPEG conversion for Kindle (`pillow` extra; skip if not installed).

7) Packaging & tooling
   - `pyproject.toml` with console entrypoint `shamela-to-epub`.
   - Dev extras: `pytest`, `ruff`, `black`.
   - `pre-commit` config for ruff/black and EOF fixes.
   - CI: lint + tests (local fixtures only).

## TDD plan (tests first)
- `tests/test_toc.py`: parse_toc returns ordered unique items from fixture.
- `tests/test_meta.py`: parse_book_meta returns clean title/author (Arabic preserved; no HTML bleed).
- `tests/test_clean.py`: content cleaning removes `span.fa`, keeps `sup`, `a[id]`.
- `tests/test_filename.py`: filename builder strips leading كتاب/الكتاب; no underscores; publisher concat.
- Parallel unit test: simulate rate limiter (fake clock) to assert max concurrency & intervals.

## Non-goals
- Do not change minimal EPUB structure (nav not in spine; no embedded fonts by default).
- No network in tests.

---
Branch: `feat/improvements-roadmap`

