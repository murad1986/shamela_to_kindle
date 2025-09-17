"""shamela_books public API (library-first).

Exports stable functions and classes for use by other applications. The CLI is
thin and delegates to internal modules.
"""
from __future__ import annotations

from .http import RateLimiter
from .parsers import ContentParser, parse_book_meta, parse_toc
from .endnotes import extract_endnotes, link_endnote_refs, build_endnotes_xhtml
from .cover import _parse_min_size, _maybe_convert_png_to_jpeg
from .builder import strip_book_prefix
from .api import build_epub_from_url
from .exceptions import ShamelaError

__all__ = [
    "RateLimiter",
    "ContentParser",
    "parse_toc",
    "parse_book_meta",
    "extract_endnotes",
    "link_endnote_refs",
    "build_endnotes_xhtml",
    "_parse_min_size",
    "_maybe_convert_png_to_jpeg",
    "strip_book_prefix",
    "build_epub_from_url",
    "ShamelaError",
]
