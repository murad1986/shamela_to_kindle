# Endnotes: Design and Implementation

Goal: clickable endnotes that work consistently on Kindle and Apple Books with no number duplication.

## Numbering

- Global numbering across the book: `G = 1..N` assigned after all chapters are fetched, in TOC order and order of appearance.
- In chapter text, we always display the global `G` (ASCII digits), regardless of source `(١)`/`(N)`.

## Extraction

- Source: one or more trailing `<p class="hamesh">` blocks with patterns:
  - `(N) text`, `[N] text`, or `N. / N- / N: text` (Arabic/Persian/Latin digits supported).
- Cleanup: bidi controls and non‑breaking spaces removed; text normalized.

## Linking

- In chapter text, replace markers with:
  - `(N)` → `<sup><a id="ref-G" href="endnotes.xhtml#note-G">G</a></sup>`.
  - `<sup>١</sup>` / `<sup>(١)</sup>` → normalized links to global `G`.
  - Existing `<sup><a>…</a></sup>` from source are normalized to `G`.
- End page: `endnotes.xhtml` uses `<ol>`; we do NOT add explicit `G.` prefix to avoid “G.G” rendering.
- Back link ↩︎ points to the exact chapter file `#ref-G`. Additionally, a backlink to the nearest `h2/h3` section is included.

## Duplicate removal

- If the source endnote text starts with a number (`16. ...`, `(١٦) ...`), strip leading numeric tokens (Arabic/Persian/Latin) and common punctuation before writing to `endnotes.xhtml`.

## Robustness

- XHTML is well‑formed: tags are properly balanced; `xmlns:epub` declared wherever `epub:type` is used.
- For Apple Books, an allowlist sanitizer removes risky `<span>/<a>` wrappers and attributes.
