from __future__ import annotations

import html
import os
import re
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin

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
from .providers import Provider, ShamelaProvider
from .sanitizer import sanitize_fragment


class BuildEvent(dict):
    """Opaque event object for progress reporting."""
    pass


def _emit(cb: Optional[Callable[[BuildEvent], None]], ev: BuildEvent) -> None:
    if cb:
        try:
            cb(ev)
        except Exception:
            # Never let callbacks break the build
            pass


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
    cover_aspect_min: float = 0.5,
    cover_aspect_max: float = 2.2,
    provider: Optional[Provider] = None,
    on_event: Optional[Callable[[BuildEvent], None]] = None,
    images_min_bytes: int = 1 * 1024,
    images_min_size: Optional[Tuple[int, int]] = (200, 200),
    profile: str = "minimal",
    use_cache: bool = True,
) -> str:
    if not re.search(r"https?://[\w.:-]+/book/\d+/?$", book_url):
        book_url = re.sub(r"/+$", "", book_url)
        if not re.search(r"https?://[\w.:-]+/book/\d+$", book_url):
            raise ShamelaError("Invalid book URL. Expected https://shamela.ws/book/<id>")
    _prov = provider or ShamelaProvider()
    index_html = _prov.fetch_index(book_url, use_cache=use_cache)
    meta = parse_book_meta(index_html)
    toc = _prov.parse_toc(book_url, index_html)
    if not toc:
        raise ShamelaError("TOC parsing returned no chapters.")
    total = len(toc) if limit is None else min(len(toc), limit)
    book_id = extract_book_id(book_url)
    base_book_url = re.sub(r"/+$", "", book_url)

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

    next_link_re = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*&nbsp;&gt;&nbsp;\s*</a>', re.I)
    page_id_re = re.compile(rf"/book/{book_id}/(\d+)")

    def _extract_body_fragment(html_text: str) -> str:
        cp = ContentParser()
        cp.feed(html_text)
        body_html = cp.get_content()
        if body_html:
            return body_html
        cleaned = re.sub(r"<div[^>]*class=\"s-nav\"[\s\S]*?</div>", "", html_text)
        m = re.search(r'<div[^>]*class="nass[^"]*"[^>]*>([\s\S]*?)</div>', cleaned)
        fallback = m.group(1) if m else ""
        return html.unescape(fallback)

    def _next_page_id(html_text: str) -> Optional[int]:
        m = next_link_re.search(html_text)
        if not m:
            return None
        href = html.unescape(m.group(1) or "").strip()
        if not href:
            return None
        mid = page_id_re.search(href)
        if not mid:
            return None
        try:
            return int(mid.group(1))
        except (TypeError, ValueError):
            return None

    next_lookup: Dict[int, Optional[int]] = {}
    for pos, item in enumerate(toc):
        nxt = toc[pos + 1].id if pos + 1 < len(toc) else None
        next_lookup[item.id] = nxt

    toc_slice = toc[:total]
    seq = []
    for idx, item in enumerate(toc_slice, start=1):
        next_id = next_lookup.get(item.id)
        seq.append((idx, (item, next_id)))

    def _page_url(pid: int) -> str:
        return urljoin(base_book_url + "/", str(pid))

    def worker(idx_item):
        idx, (it, next_chapter_id) = idx_item
        _emit(on_event, BuildEvent(type="chapter_fetch_start", index=idx, id=it.id))
        current_id = it.id
        current_url = it.url
        seen_ids: set[int] = set()
        fragments: List[str] = []
        title: Optional[str] = None
        guard = 0
        while True:
            if current_id in seen_ids:
                break
            seen_ids.add(current_id)
            limiter.wait()
            html_text = _prov.fetch_chapter(current_url, referer=book_url, use_cache=use_cache)
            if title is None:
                title = extract_title_from_page(html_text) or it.title
            fragment = _extract_body_fragment(html_text)
            if fragment:
                fragments.append(fragment)
            guard += 1
            if guard > 6000:
                break
            next_pid = _next_page_id(html_text)
            if not next_pid:
                break
            if next_chapter_id is not None and next_pid >= next_chapter_id:
                break
            if next_pid in seen_ids:
                break
            current_id = next_pid
            current_url = _page_url(next_pid)
        combined_html = "".join(fragments)
        body_wo, notes = extract_endnotes(combined_html)
        if not body_wo or len(body_wo) < 10:
            sanitized = sanitize_fragment(combined_html, profile=profile)
            body_wo, notes = extract_endnotes(sanitized)
        _emit(on_event, BuildEvent(type="chapter_fetch_done", index=idx, id=it.id))
        return (idx, _ChapterRaw(it.id, it.order + 2, title or it.title, body_wo, notes))

    items = seq
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
                got = _download_bytes(cand, use_cache=use_cache)
                if not got:
                    continue
                data, ctype = got
                if ctype not in ("image/jpeg", "image/jpg", "image/png"):
                    continue
                size = _image_size(data)
                if not size:
                    continue
                w, h = size
                aspect = (w / h) if h else 0.0
                if (
                    min(w, h) < min(wmin, hmin)
                    or len(data) < min_bytes
                    or (aspect and (aspect < float(cover_aspect_min) or aspect > float(cover_aspect_max)))
                ):
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
    # Collect sub-TOC per chapter and inline images for embedding
    subnav_by_chapter: Dict[int, List[Tuple[str, str]]] = {}
    image_assets: List[Tuple[str, bytes, str]] = []  # (basename, data, mime)
    img_counter = 1
    gid_to_section_id: Dict[int, str] = {}
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
        sanitized = sanitize_fragment(raw.body_wo, profile=profile)
        # Rewrite and embed images
        def _embed_images(html_in: str) -> str:
            nonlocal img_counter
            def repl(m: re.Match) -> str:
                nonlocal img_counter
                tag = m.group(0)
                src = m.group(1)
                alt = m.group(2) or ""
                if not src or not re.match(r"https?://", src):
                    return tag
                got = _download_bytes(src, use_cache=use_cache)
                if not got:
                    return tag
                data, ctype = got
                if ctype not in ("image/jpeg", "image/jpg", "image/png"):
                    return tag
                if len(data) < max(0, int(images_min_bytes)):
                    return tag
                size = _image_size(data)
                if size:
                    w, h = size
                    if images_min_size is not None:
                        wmin, hmin = images_min_size
                        if min(w, h) < min(wmin, hmin):
                            return tag
                ext = 'png' if (ctype == 'image/png' or src.lower().endswith('.png')) else 'jpg'
                base = f"img{img_counter:04d}.{ext}"
                img_counter += 1
                # Avoid duplicates by simple content hash-like check (size + first bytes)
                # (minimal; real impl could hash)
                image_assets.append((base, data, 'image/png' if ext == 'png' else 'image/jpeg'))
                new_src = f"../images/{base}"
                return f"<img src=\"{new_src}\" alt=\"{html.escape(alt)}\" />"
            # Capture img with src and optional alt
            return re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*?(?:alt=\"([^\"]*)\")?[^>]*/?>", repl, html_in, flags=re.I)

        sanitized = _embed_images(sanitized)
        # Add ids to h2/h3 and collect sub-TOC
        def _add_ids_to_headings(html_in: str) -> Tuple[str, List[Tuple[str, str]]]:
            sub = []
            idx_local = 1
            def add_id(m: re.Match) -> str:
                nonlocal idx_local
                tag = m.group(1).lower()
                inner = m.group(2)
                # Strip tags inside heading, keep text for anchor title
                inner_txt = re.sub(r"<[^>]+>", "", inner)
                inner_txt = norm_ar_text(inner_txt)
                aid = f"sec-{raw.id}-{idx_local}"
                idx_local += 1
                sub.append((aid, inner_txt))
                return f"<{tag} id=\"{aid}\">{inner}</{tag}>"
            out = re.sub(r"<(h2|h3)\b[^>]*>([\s\S]*?)</\1>", add_id, html_in, flags=re.I)
            return out, sub

        linked_body = link_endnote_refs(sanitized, local_map) if local_map else sanitized
        linked_body, sub = _add_ids_to_headings(linked_body)
        # Map each gid to nearest preceding section (h2/h3) within this chapter
        if local_map:
            # Build list of headings in document order
            heads = [(m.start(), m.group(1)) for m in re.finditer(r"<(?:h2|h3)\b[^>]*id=\"([^\"]+)\"[^>]*>", linked_body, flags=re.I)]
            heads.sort()
            def nearest_section(pos: int) -> Optional[str]:
                cur = None
                for hp, hid in heads:
                    if hp <= pos:
                        cur = hid
                    else:
                        break
                return cur
            # Find positions of ref anchors and map to section id
            for mref in re.finditer(r"id=\"ref-(\d+)\"", linked_body):
                gid = int(mref.group(1))
                sec = nearest_section(mref.start())
                if sec:
                    gid_to_section_id[gid] = sec
        if sub:
            subnav_by_chapter[raw.id] = sub
        xhtml = build_chapter_xhtml_min(raw.title, linked_body)
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
        inline_images=image_assets if image_assets else None,
        subnav_by_chapter=subnav_by_chapter if subnav_by_chapter else None,
        endnote_gid_to_section_id=gid_to_section_id if gid_to_section_id else None,
    )
    return out_path


def fetch_toc(book_url: str, *, provider: Optional[Provider] = None) -> List[Tuple[int, str, str]]:
    """Fetch index HTML and return TOC items as tuples (id, title, url) in order."""
    _prov = provider or ShamelaProvider()
    index_html = _prov.fetch_index(book_url)
    items = _prov.parse_toc(book_url, index_html)
    return [(it.id, it.title, it.url) for it in items]


def fetch_chapter(book_url: str, chapter_url: str, *, provider: Optional[Provider] = None) -> str:
    _prov = provider or ShamelaProvider()
    return _prov.fetch_chapter(chapter_url, referer=book_url)
