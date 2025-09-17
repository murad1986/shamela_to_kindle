from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TocItem:
    id: int
    order: int
    title: str
    url: str
    aliases: List[str]


@dataclass
class Chapter:
    id: int
    order: int
    title: str
    xhtml: str  # well-formed xhtml body content


@dataclass
class BookMeta:
    title: str
    book_title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    pages: Optional[str] = None
    author_page: Optional[str] = None
    language: str = "ar"
    identifier: str = dataclasses.field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")

