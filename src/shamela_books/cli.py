from __future__ import annotations

"""Thin CLI delegating to the legacy script's main() for now.

Keeps a stable public entrypoint at `shamela_books.cli:main` while we migrate
implementation fully into the library.
"""

from typing import Optional, List
import argparse
import os
import sys

from .api import build_epub_from_url
from .exceptions import ShamelaError
from .builder import make_title_filename, strip_book_prefix
from .http import fetch
from .parsers import parse_book_meta


def main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover
    ap = argparse.ArgumentParser(description="Download a Shamela book and build minimal EPUB3 (RTL, Kindle-friendly)")
    ap.add_argument("url", help="Book URL like https://shamela.ws/book/158")
    ap.add_argument("-o", "--output", help="Output EPUB path (default: output/<book title>.epub)")
    ap.add_argument("--throttle", type=float, default=0.8, help="Delay between requests in seconds")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of chapters for a quick run")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--cover-auto", action="store_true", help="Fetch Google Images result as cover (best-effort)")
    group.add_argument("--cover", help="Path to local cover image (jpg/png)")
    ap.add_argument("--cover-query", help="Override cover search query (used with --cover-auto)")
    ap.add_argument("--cover-min-size", help="Minimal cover size WxH (e.g., 600x800)")
    ap.add_argument("--cover-min-bytes", type=int, default=50 * 1024, help="Minimal cover file size in bytes")
    ap.add_argument("--cover-convert-jpeg", action="store_true", help="Convert PNG cover to JPEG (requires Pillow)")
    ap.add_argument("--workers", type=int, default=2, help="Parallel workers (polite): 1–4 recommended")
    ap.add_argument("--jitter", type=float, default=0.3, help="Throttle jitter fraction (0..1)")
    ap.add_argument("--profile", choices=["minimal", "kindle", "apple"], default="minimal", help="Sanitizer/semantics profile")
    ap.add_argument("--no-cache", action="store_true", help="Disable local HTTP/image cache")
    args = ap.parse_args(argv)

    try:
        out_path = args.output
        if not out_path:
            index_html = fetch(args.url)
            meta = parse_book_meta(index_html)
            title = strip_book_prefix(meta.book_title or meta.title)
            combo = f"{title} - {meta.publisher}" if meta.publisher else title
            base_name = make_title_filename(combo)
            out_path = os.path.join('output', base_name + '.epub')

        cover_auto = args.cover_auto or (not args.cover and not args.cover_auto)
        cover_min_size = None
        if args.cover_min_size:
            try:
                w, h = [int(x) for x in args.cover_min_size.lower().split('x')]
                cover_min_size = (w, h)
            except Exception:
                cover_min_size = None
        def on_event(ev: dict) -> None:
            # Simple CLI progress feedback without polluting library API
            t = ev.get("type")
            if t == "chapter_fetch_start":
                print(f"[ {ev.get('index'):03d} ] id={ev.get('id')} …", end="", flush=True)
            elif t == "chapter_fetch_done":
                print(" ok")

        build_epub_from_url(
            args.url,
            out_path,
            throttle=args.throttle,
            limit=args.limit,
            cover_auto=bool(cover_auto),
            cover_path=args.cover,
            cover_convert_jpeg=bool(args.cover_convert_jpeg),
            workers=max(1, args.workers),
            jitter=max(0.0, min(1.0, args.jitter)),
            cover_query=args.cover_query,
            cover_min_size=cover_min_size,
            cover_min_bytes=max(0, int(args.cover_min_bytes)),
            profile=args.profile,
            use_cache=not args.no_cache,
            on_event=on_event,
        )
        print("[✓] Done.")
        return 0
    except ShamelaError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"[!] Error: {e}", file=sys.stderr)
        return 2
