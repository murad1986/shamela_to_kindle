# Apple Books Compatibility

Apple Books validates XHTML as strict XML and is sensitive to namespaces and tag nesting.

## Requirements & Solutions

- EPUB namespace:
  - Wherever `epub:type` is used, root `<html>` declares
    `xmlns:epub="http://www.idpf.org/2007/ops"`.
  - Applied to chapters, `nav.xhtml`, and `endnotes.xhtml`.

- Strict XML validity:
  - Source contains `<span>`/`<a>` wrappers (copy buttons/anchors) that break nesting.
  - We remove all source `<span>` and `<a>` preserving a small allowlist: `p, br, strong, em, b, i, h1..h6, blockquote, ul, ol, li, sup, sub`.
  - Content parser closes tags in correct order; a fallback allowlist sanitizer is applied before writing.

- Endnotes:
  - In text: global `G` linking to `endnotes.xhtml#note-G`.
  - End page: `<ol>` renders numbers; we do not prepend custom `G.` to avoid “G.G”.
  - Back link ↩︎ returns to the exact chapter position.

## Verification

- Internal: each chapter XHTML is parsed by an XML parser (well‑formed check) to prevent nesting errors.
- On device: remove the previous imported book before re‑import (Books caches content).

## Known limitations

- `epub:type` is preserved; semantic richness is not required for Apple Books — valid XML is.
- If the source adds new wrappers/classes, we may extend the allowlist sanitizer.

