from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Optional

from .http import fetch
from .models import TocItem
from .parsers import parse_toc


class Provider(Protocol):
    def fetch_index(self, url: str, *, use_cache: bool = True) -> str:  # returns HTML
        ...

    def fetch_chapter(self, url: str, *, referer: Optional[str] = None, use_cache: bool = True) -> str:  # returns HTML
        ...

    def parse_toc(self, book_url: str, index_html: str) -> List[TocItem]:
        ...


class ShamelaProvider:
    """Default provider for shamela.ws-like sites."""

    def fetch_index(self, url: str, *, use_cache: bool = True) -> str:
        return fetch(url, use_cache=use_cache)

    def fetch_chapter(self, url: str, *, referer: Optional[str] = None, use_cache: bool = True) -> str:
        return fetch(url, referer=referer, use_cache=use_cache)

    def parse_toc(self, book_url: str, index_html: str) -> List[TocItem]:
        return parse_toc(book_url, index_html)
