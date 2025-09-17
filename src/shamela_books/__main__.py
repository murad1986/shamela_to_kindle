"""Module entrypoint to run as `python -m shamela_books`."""
from __future__ import annotations

from .cli import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
