from __future__ import annotations


class ShamelaError(Exception):
    """Base user-facing error for shamela_books.

    Use this for predictable, actionable failures (bad URL, invalid cover, etc.).
    CLI will catch this and print a concise message without a traceback.
    """


class CoverError(ShamelaError):
    """Problems handling cover image (invalid format, too small, unreadable)."""


class FetchError(ShamelaError):
    """Network retrieval error for book pages or assets."""

