from __future__ import annotations

import html
import os
import re
import threading
from typing import List, Optional, Tuple

from .http import fetch, RateLimiter
from .models import BookMeta, Chapter
from .parsers import parse_book_meta, parse_toc, ContentParser
from .parsers import extract_book_id  # re-exported helper
from .exceptions import ShamelaError, CoverError
from .utils import norm_ar_text
from .endnotes import extract_endnotes, link_endnote_refs, build_endnotes_xhtml
from .builder import build_chapter_xhtml_min, write_epub3, make_title_filename, strip_book_prefix
from .cover import (
    _image_urls_from_google,
    _image_urls_from_duckduckgo,
    _image_urls_from_bing,
    _download_bytes,
    _image_size,
    _maybe_convert_png_to_jpeg,
)


def extract_title_from_page(html_text: str) -> Optional[str]:
    m = re.search(r"<div[^>]*class=\"s-nav\"[\s\S]*?<a[^>]*class=\"active\"[^>]*>(.*?)</a>", html_text)
    if m:
        return norm_ar_text(html.unescape(m.group(1)))
    m2 = re.search(r"<section[^>]*page-header[\s\S]*?<h1[^>]*>[\s\S]*?</h1>", html_text)
    if m2:
        inner = re.sub(r"<.*?>", "", m2.group(0))
        return norm_ar_text(html.unescape(inner))
    mt = re.search(r"<title>(.*?)</title>", html_text)
    if mt:
        t = norm_ar_text(html.unescape(mt.group(1)))
        t = re.sub(r"\s*-\s*المكتبة الشاملة.*$", "", t)
        return t
    return None


def build_epub_from_url(
    book_url: str,
    out_path: Optional[str] = None,
    *,
    throttle: float = 0.8,
    limit: Optional[int] = None,
    cover_auto: bool = False,
    cover_path: Optional[str] = None,
    cover_convert_jpeg: bool = False,
    workers: int = 2,
    jitter: float = 0.3,
    cover_query: Optional[str] = None,
    cover_min_size: Optional[Tuple[int, int]] = None,
    cover_min_bytes: int = 50 * 1024,
) -> str:
    if not re.search(r"https?://[\w.:-]+/book/\d+/?$", book_url):
        book_url = re.sub(r"/+$", "", book_url)
        if not re.search(r"https?://[\w.:-]+/book/\d+$", book_url):
            raise ShamelaError("Invalid book URL. Expected https://shamela.ws/book/<id>")
    index_html = fetch(book_url)
    meta = parse_book_meta(index_html)
    toc = parse_toc(book_url, index_html)
    if not toc:
        raise ShamelaError("TOC parsing returned no chapters.")
    total = len(toc) if limit is None else min(len(toc), limit)

    print_lock = threading.Lock()
    limiter = RateLimiter(throttle, jitter=jitter)

    class _ChapterRaw:
        __slots__ = ("id", "order", "title", "body_wo", "notes")
        def __init__(self, id: int, order: int, title: str, body_wo: str, notes: list[tuple[str, str]]):
            self.id = id
            self.order = order
            self.title = title
            self.body_wo = body_wo
            self.notes = notes

    fetched: dict[int, _ChapterRaw] = {}

    def worker(idx_item):
        idx, it = idx_item
        with print_lock:
            print(f"[ {idx:03d}/{total:03d} ] id={it.id} …", end="", flush=True)
        limiter.wait()
        html_text = fetch(it.url, referer=book_url)
        title = extract_title_from_page(html_text) or it.title
        cp = ContentParser(); cp.feed(html_text)
        body_html = cp.get_content()
        if not body_html:
            cleaned = re.sub(r"<div[^>]*class=\"s-nav\"[\s\S]*?</div>", "", html_text)
            m = re.search(r'<div[^>]*class="nass[^"]*"[^>]*>([\s\S]*?)</div>', cleaned)
            body_html = m.group(1) if m else ""
            body_html = html.unescape(body_html)
        body_wo, notes = extract_endnotes(body_html)
        if not body_wo or len(body_wo) < 10:
            # Fallback sanitizer for Apple Books strictness
            body_wo = sanitize_fragment_allowlist(body_html)
            body_wo, notes = extract_endnotes(body_wo)
        with print_lock:
            print(" ok")
        return (idx, _ChapterRaw(it.id, it.order + 2, title, body_wo, notes))

    items = list(enumerate(toc[:total], start=1))
    if workers <= 1:
        for idx_item in items:
            idx, raw = worker(idx_item)
            fetched[idx] = raw
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {ex.submit(worker, idx_item): idx_item for idx_item in items}
            for fut in as_completed(futs):
                idx, raw = fut.result()
                fetched[idx] = raw

    if not out_path:
        title = strip_book_prefix(meta.book_title or meta.title)
        combo = f"{title} - {meta.publisher}" if meta.publisher else title
        base_name = make_title_filename(combo)
        out_path = os.path.join('output', base_name + '.epub')

    cover_asset = None
    # Local cover overrides auto search
    if cover_path:
        try:
            with open(cover_path, 'rb') as fh:
                data = fh.read()
            size = _image_size(data)
            if not size:
                raise ValueError("Unrecognized image format for cover (only PNG/JPEG supported)")
            w, h = size
            wmin, hmin = cover_min_size or (300, 300)
            if min(w, h) < min(wmin, hmin) or len(data) < max(0, int(cover_min_bytes)):
                raise ValueError("Cover image too small (dimensions or bytes)")
            ext = os.path.splitext(cover_path)[1].lower()
            cover_mime = 'image/png' if ext == '.png' else 'image/jpeg'
            if cover_convert_jpeg and cover_mime == 'image/png':
                data, cover_mime = _maybe_convert_png_to_jpeg(data, cover_mime)
            cover_name = 'cover.png' if cover_mime == 'image/png' else 'cover.jpg'
            cover_asset = (cover_name, data, cover_mime)
        except Exception as e:
            raise CoverError(f"Failed to read local cover: {e}")
    elif cover_auto:
        min_bytes = max(0, int(cover_min_bytes))
        wmin, hmin = cover_min_size or (300, 300)
        base_q = meta.book_title or meta.title
        q_candidates = [cover_query] if cover_query else [
            f"{base_q} cover",
            f"{base_q} book cover",
            f"{base_q} غلاف",
        ]
        providers = [
            _image_urls_from_google,
            _image_urls_from_duckduckgo,
            _image_urls_from_bing,
        ]
        img_url = None
        for q in q_candidates:
            candidates: List[str] = []
            for prov in providers:
                candidates.extend(prov(q, max_n=6))
            for cand in candidates:
                got = _download_bytes(cand)
                if not got:
                    continue
                data, ctype = got
                if ctype not in ("image/jpeg", "image/jpg", "image/png"):
                    continue
                size = _image_size(data)
                if not size:
                    continue
                w, h = size
                if min(w, h) < min(wmin, hmin) or len(data) < min_bytes:
                    continue
                ext = 'png' if ('png' in ctype or cand.lower().endswith('.png')) else 'jpg'
                cover_name = f"cover.{ext}"
                cover_mime = 'image/png' if ext == 'png' else 'image/jpeg'
                if cover_convert_jpeg:
                    data, cover_mime = _maybe_convert_png_to_jpeg(data, cover_mime)
                cover_asset = (cover_name, data, cover_mime)
                img_url = cand
                break
            if img_url:
                print(f"[+] Cover image fetched: {img_url}")
                break
        if not img_url:
            print("[!] No suitable cover image found (size filter)")

    # Assign global numbering deterministically in reading order
    chapters: List[Chapter] = []
    global_notes: List[tuple[int, str]] = []
    gid_to_chapter_id: dict[int, int] = {}
    next_gid = 1
    chapter_local_to_gid: dict[int, dict[str, int]] = {}
    for idx, _ in items:
        raw = fetched.get(idx)
        if not raw:
            continue
        local_map: dict[str, int] = {}
        for num_ascii, text in raw.notes:
            gid = next_gid
            next_gid += 1
            local_map[num_ascii] = gid
            global_notes.append((gid, text))
            gid_to_chapter_id[gid] = raw.id
        chapter_local_to_gid[raw.id] = local_map
        sanitized = sanitize_fragment_allowlist(raw.body_wo)
        linked = link_endnote_refs(sanitized, local_map) if local_map else sanitized
        xhtml = build_chapter_xhtml_min(raw.title, linked)
        chapters.append(Chapter(id=raw.id, order=raw.order, title=raw.title, xhtml=xhtml))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    write_epub3(
        meta,
        chapters,
        out_path,
        minimal_profile=True,
        cover_asset=cover_asset,
        endnotes_entries=global_notes if global_notes else None,
        endnote_gid_to_chapter_id=gid_to_chapter_id if global_notes else None,
    )
    return out_path
