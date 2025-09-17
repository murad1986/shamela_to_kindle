#!/usr/bin/env python3
"""
Shamela book → EPUB generator (RTL-aware).

Usage:
  python scripts/shamela_to_epub.py https://shamela.ws/book/158 -o output/book_158.epub

Dependencies: standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import html
import io
import os
import re
import sys
import time
import unicodedata as ud
import uuid
import xml.sax.saxutils as xsu
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse, quote_plus
from urllib.request import Request, urlopen
import zipfile


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


# -----------------------------
# Models
# -----------------------------


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
    # Title detected from header (<h1>/<title>)
    title: str
    # Precise title from metadata block "الكتاب: ..." (preferred)
    book_title: Optional[str] = None
    # Author (from "المؤلف: ...")
    author: Optional[str] = None
    # Optional extra metadata
    publisher: Optional[str] = None
    edition: Optional[str] = None
    pages: Optional[str] = None
    author_page: Optional[str] = None
    language: str = "ar"
    identifier: str = dataclasses.field(default_factory=lambda: f"urn:uuid:{uuid.uuid4()}")


# -----------------------------
# Utils
# -----------------------------


BIDI_CTRL = {
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
}


def norm_ar_text(s: str) -> str:
    """Normalize Arabic titles for display while preserving diacritics.
    - Decode entities
    - Remove bidi control/tatweel/soft hyphen
    - NFKC normalize
    - Collapse whitespace
    """
    if not s:
        return s
    s = html.unescape(s)
    s = s.replace("\u00A0", " ").replace("\u202F", " ").replace("\u00AD", "")
    s = "".join(ch for ch in s if ch not in BIDI_CTRL)
    s = s.replace("\u0640", "")  # tatweel
    s = ud.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.strip()


def fetch(url: str, *, referer: Optional[str] = None, retry: int = 3, sleep: float = 1.0) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(retry):
        try:
            req = Request(url, headers={
                "User-Agent": UA,
                "Accept-Language": "ar,en;q=0.8",
                "Referer": referer or url,
            })
            with contextlib.closing(urlopen(req, timeout=20)) as resp:
                data = resp.read()
            # site is utf-8
            return data.decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt + 1 < retry:
                time.sleep(sleep * (2 ** attempt))
            continue
    assert last_err is not None
    raise last_err


# -----------------------------
# Parsing
# -----------------------------


class AnchorParser(HTMLParser):
    """Collect anchors and text in-order."""

    def __init__(self):
        super().__init__()
        self.in_a = False
        self.href = None
        self.buf = []
        self.result: List[Tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            self.in_a = True
            self.href = href
            self.buf = []

    def handle_data(self, data):
        if self.in_a:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            text = norm_ar_text("".join(self.buf))
            self.result.append((self.href or "", text))
            self.in_a = False
            self.href = None
            self.buf = []


def parse_book_meta(html_text: str) -> BookMeta:
    # Title from <h1> or <title>
    m = re.search(r"<h1[^>]*>\s*<a[^>]*>(.*?)</a>\s*</h1>", html_text, flags=re.S)
    title = norm_ar_text(html.unescape(m.group(1))) if m else None
    if not title:
        mt = re.search(r"<title>(.*?)</title>", html_text, flags=re.S)
        title = norm_ar_text(html.unescape(mt.group(1))) if mt else "كتاب من الشاملة"
    # Try to narrow to the "بطاقة الكتاب" block only
    mblock = re.search(r"بطاقة\s*الكتاب[\s\S]*?</h3>([\s\S]*?)<div[^>]*class=\"text-left", html_text)
    scope = mblock.group(1) if mblock else html_text

    # Extract detailed metadata block (بطاقة الكتاب)
    def _extract(label: str, where: str) -> Optional[str]:
        m = re.search(label + r"\s*:?\s*(.*?)<br\s*/?>", where)
        if m:
            return norm_ar_text(html.unescape(m.group(1)))
        return None

    book_title = _extract("الكتاب", scope)
    author_full = _extract("المؤلف", scope)
    publisher = _extract("الناشر", scope)
    edition = _extract("الطبعة", scope)
    pages = _extract("عدد الصفحات", scope)
    # Author page name inside brackets
    ma2 = re.search(r"صفحة\s*المؤلف:\s*\[\s*<a[^>]*>(.*?)</a>\s*]\s*", html_text)
    author_page = norm_ar_text(html.unescape(ma2.group(1))) if ma2 else None

    # Fallback author: try bracketed author near header if full not found
    if not author_full:
        ma = re.search(r"\[\s*<a[^>]*>(.*?)</a>\s*]\s*", html_text)
        author_full = norm_ar_text(html.unescape(ma.group(1))) if ma else None

    return BookMeta(
        title=title,
        book_title=book_title,
        author=author_full,
        publisher=publisher,
        edition=edition,
        pages=pages,
        author_page=author_page,
    )


def extract_book_id(url: str) -> str:
    m = re.search(r"/book/(\d+)", url)
    if not m:
        raise ValueError("URL must be like https://shamela.ws/book/<id>")
    return m.group(1)


def parse_toc(book_url: str, html_text: str) -> List[TocItem]:
    base = f"https://{urlparse(book_url).hostname}"
    book_id = extract_book_id(book_url)

    p = AnchorParser()
    p.feed(html_text)

    items: List[Tuple[int, str, str]] = []
    seen_href = set()
    for href, text in p.result:
        if not href:
            continue
        if href.startswith("/"):
            href = urljoin(base, href)
        if f"/book/{book_id}/" not in href:
            continue
        m = re.search(rf"/book/{book_id}/(\d+)$", href)
        if not m:
            continue
        if href in seen_href:
            continue
        seen_href.add(href)
        if not text:
            continue
        items.append((int(m.group(1)), text, href))

    by_id: dict[int, TocItem] = {}
    order: List[int] = []
    for id_, text, href in items:
        if id_ not in by_id:
            by_id[id_] = TocItem(id=id_, order=len(order) + 1, title=text, url=href, aliases=[])
            order.append(id_)
        else:
            if text != by_id[id_].title and text not in by_id[id_].aliases:
                by_id[id_].aliases.append(text)

    return [by_id[i] for i in order]


class ContentParser(HTMLParser):
    """Extract main content container: prefer div.nass; otherwise the largest text block.
    Also strip scripts/styles/nav.
    """

    def __init__(self):
        super().__init__()
        self.out = io.StringIO()
        self.stack: List[Tuple[str, dict]] = []
        self.capture = False
        self.depth_capture = 0
        self.best_html = ""
        self.best_len = 0
        self.tmp_buf = io.StringIO()
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        self.stack.append((tag, attrs_d))
        cls = attrs_d.get("class", "")
        if not self.capture and tag == "div" and ("nass" in cls.split() or "nass" in cls):
            self.capture = True
            self.depth_capture = 1
            self.tmp_buf = io.StringIO()
        elif self.capture:
            self.depth_capture += 1
        # Skip script/style/nav blocks entirely
        if tag in {"script", "style"}:
            return

        if self.capture:
            # Allow basic tags; convert relative links to text
            # Skip UI cruft: buttons/icons (fa), while keeping anchors/ids
            cls = attrs_d.get("class", "")
            classes = set(cls.split()) if isinstance(cls, str) else set()
            is_icon = any(c.startswith("fa") for c in classes) or tag in {"i"}
            is_button = tag == "button" or any(c.startswith("btn") for c in classes)
            if self.skip_depth > 0 or is_icon or is_button:
                self.skip_depth += 1
                return
            allowed = {"p", "br", "span", "strong", "em", "b", "i", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol", "li", "sup", "sub", "a"}
            if tag in allowed:
                attrs_str = "".join(
                    f" {k}={xsu.quoteattr(v)}" for k, v in attrs if k in {"id", "class"}
                )
                self.tmp_buf.write(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            return

        if self.capture:
            if self.skip_depth > 0:
                self.skip_depth -= 1
                return
            if tag in {"p", "span", "strong", "em", "b", "i", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol", "li", "sup", "sub", "a"}:
                self.tmp_buf.write(f"</{tag}>")

            self.depth_capture -= 1
            if self.depth_capture == 0:
                self.capture = False
                html_part = self.tmp_buf.getvalue()
                L = len(re.sub(r"\s+", " ", html_part))
                if L > self.best_len:
                    self.best_len = L
                    self.best_html = html_part

        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self.capture and self.skip_depth == 0:
            self.tmp_buf.write(xsu.escape(data))

    def get_content(self) -> str:
        return self.best_html.strip()


def extract_title_from_page(html_text: str) -> Optional[str]:
    # Try active entry in side nav
    m = re.search(r"<div[^>]*class=\"s-nav\"[\s\S]*?<a[^>]*class=\"active\"[^>]*>(.*?)</a>", html_text)
    if m:
        return norm_ar_text(html.unescape(m.group(1)))
    # Fallback to <h1> sub-title
    m2 = re.search(r"<section[^>]*page-header[\s\S]*?<h1[^>]*>[\s\S]*?</h1>", html_text)
    if m2:
        inner = re.sub(r"<.*?>", "", m2.group(0))
        return norm_ar_text(html.unescape(inner))
    # Last resort: document title
    mt = re.search(r"<title>(.*?)</title>", html_text)
    if mt:
        t = norm_ar_text(html.unescape(mt.group(1)))
        # Strip site suffix
        t = re.sub(r"\s*-\s*المكتبة الشاملة.*$", "", t)
        return t
    return None


def build_chapter_xhtml(title: str, body_html: str, lang: str = "ar") -> str:
    title_xml = xsu.escape(title)
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <title>%s</title>\n"
        "  <link rel=\"stylesheet\" type=\"text/css\" href=\"../css/style.css\"/>\n"
        "</head>\n"
        "<body>\n"
        "  <section epub:type=\"chapter\">\n"
        "    <h1 class=\"chapter-title\">%s</h1>\n"
        "    <div class=\"chapter-body\">%s</div>\n"
        "  </section>\n"
        "</body>\n"
        "</html>\n"
    ) % (lang, lang, title_xml, title_xml, body_html)


def build_chapter_xhtml_min(title: str, body_html: str, lang: str = "ar") -> str:
    """Minimal EPUB3 XHTML (matches Kindle-accepted sample)."""
    title_xml = xsu.escape(title)
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <title>%s</title>\n"
        "  <link rel=\"stylesheet\" type=\"text/css\" href=\"../css/style.css\"/>\n"
        "</head>\n"
        "<body>\n"
        "  <section epub:type=\"chapter\">\n"
        "    <h1 class=\"chapter-title\">%s</h1>\n"
        "    <div class=\"chapter-body\">%s</div>\n"
        "  </section>\n"
        "</body>\n"
        "</html>\n"
    ) % (lang, lang, title_xml, title_xml, body_html)


def build_cover_xhtml(meta: BookMeta) -> str:
    title = xsu.escape(meta.book_title or meta.title)
    author = xsu.escape(meta.author or "")
    body = (
        f"<div class=\"cover-wrap\">"
        f"<h1 class=\"cover-title\">{title}</h1>"
        f"<div class=\"cover-author\">{author}</div>"
        f"</div>"
    )
    css_extra = (
        ".cover-wrap{display:flex;flex-direction:column;justify-content:center;align-items:flex-end;"
        "min-height:90vh;padding:2rem 1rem;gap:1rem;}"
        ".cover-title{font-size:2rem;line-height:1.4;margin:0;text-align:right;}"
        ".cover-author{font-size:1.2rem;color:#444;}"
    )
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <title>%s</title>\n"
        "  <link rel=\"stylesheet\" type=\"text/css\" href=\"../css/style.css\"/>\n"
        "  <style>%s</style>\n"
        "</head>\n"
        "<body>\n%s\n"
        "</body>\n"
        "</html>\n"
    ) % (meta.language, meta.language, title, css_extra, body)


def build_info_xhtml(meta: BookMeta) -> str:
    def row(label: str, value: Optional[str]) -> str:
        if not value:
            return ""
        return f"<p><strong>{xsu.escape(label)}:</strong> {xsu.escape(value)}</p>"

    content = (
        row("الكتاب", meta.book_title or meta.title)
        + row("المؤلف", meta.author)
        + row("الناشر", meta.publisher)
        + row("الطبعة", meta.edition)
        + row("عدد الصفحات", meta.pages)
        + (f"<p><strong>صفحة المؤلف:</strong> {xsu.escape(meta.author_page)}" + "</p>" if meta.author_page else "")
    )
    body = f"<section><h1>بطاقة الكتاب</h1>{content}</section>"
    return build_chapter_xhtml("بطاقة الكتاب", body, lang=meta.language)


def make_slug(s: str) -> str:
    s = re.sub(r"[\s\u200f\u200e\u202a-\u202e]+", "-", s.strip())
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.U)
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "chapter"


def make_title_filename(title: str) -> str:
    """Make a safe filename from book title, preserving Arabic letters."""
    t = norm_ar_text(title)
    # Replace path separators and control chars
    t = t.replace('/', '-').replace('\\', '-').replace(':', ' - ')
    t = t.replace('*', ' ').replace('?', ' ').replace('"', "'").replace('<', '(').replace('>', ')').replace('|', '-').strip()
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    # Limit length to avoid OS limits
    if len(t) > 120:
        t = t[:120].rstrip()
    # Ensure not empty
    return t or 'book'


def strip_book_prefix(title: str) -> str:
    """Remove leading Arabic 'كتاب'/'الكتاب' tokens from a title for filenames."""
    s = norm_ar_text(title)
    s = re.sub(r'^\s*(?:ال)?كتاب\s*[:\-–—]?\s*', '', s)
    return s.strip() or title


# -----------------------------
# EPUB builder
# -----------------------------


def _guess_font_meta(filename: str) -> tuple[str, str, str]:
    """Return (family, weight, style) guessed from filename.
    E.g., Amiri-Regular.ttf -> (Amiri, 400, normal), Amiri-BoldItalic -> (Amiri, 700, italic)
    """
    base = os.path.basename(filename)
    name, _ext = os.path.splitext(base)
    # Split by '-' to separate family and style
    if '-' in name:
        family, style_part = name.split('-', 1)
    else:
        family, style_part = name, 'Regular'
    sp = style_part.lower()
    weight = '400'
    style = 'normal'
    if 'bold' in sp:
        weight = '700'
    if 'black' in sp or 'heavy' in sp:
        weight = '900'
    if 'semibold' in sp or 'demibold' in sp:
        weight = '600'
    if 'medium' in sp:
        weight = '500'
    if 'light' in sp:
        weight = '300'
    if 'thin' in sp or 'hairline' in sp:
        weight = '100'
    if 'italic' in sp or 'oblique' in sp:
        style = 'italic'
    return family, weight, style


def _font_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        '.ttf': 'font/ttf',
        '.otf': 'font/otf',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
    }.get(ext, 'application/octet-stream')


def write_epub3(meta: BookMeta, chapters: List[Chapter], out_path: str, *, font_files: Optional[List[str]] = None, minimal_profile: bool = False, cover_asset: Optional[Tuple[str, bytes, str]] = None):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    book_id = meta.identifier

    # Prepare in-memory files
    mimetype = b"application/epub+zip"
    container_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">\n"
        "  <rootfiles>\n"
        "    <rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/>\n"
        "  </rootfiles>\n"
        "</container>\n"
    ).encode("utf-8")

    # Prepare @font-face rules if fonts are provided
    font_faces: List[str] = []
    manifest_fonts: List[str] = []
    font_families_order: List[str] = []
    font_files = font_files or []
    for fpath in font_files:
        try:
            with open(fpath, 'rb') as fh:
                data = fh.read()
        except OSError:
            continue
        base = os.path.basename(fpath)
        family, weight, style = _guess_font_meta(base)
        if family not in font_families_order:
            font_families_order.append(family)
        src_url = f"../fonts/{base}"
        fmt = os.path.splitext(base)[1].lower().lstrip('.')
        if fmt == 'ttf':
            fmt_str = "format('truetype')"
        elif fmt == 'otf':
            fmt_str = "format('opentype')"
        elif fmt == 'woff':
            fmt_str = "format('woff')"
        elif fmt == 'woff2':
            fmt_str = "format('woff2')"
        else:
            fmt_str = ""
        font_faces.append(
            "@font-face { font-family: '" + xsu.escape(family) + "'; src: url('" + xsu.escape(src_url) + "') " + fmt_str + "; font-weight: " + weight + "; font-style: " + style + "; font-display: swap; }"
        )
        manifest_fonts.append(base)
        # store file later in zip
        # We'll reuse text_files-like list
        if 'embed_fonts_payload' not in locals():
            embed_fonts_payload = []  # type: ignore[var-annotated]
        embed_fonts_payload.append((base, data, _font_mime(base)))  # type: ignore[arg-type]

    body_fonts = ", ".join([f"'{xsu.escape(f)}'" for f in font_families_order] + ["'Amiri'", "'Noto Naskh Arabic'", "serif"]) or "'Amiri', 'Noto Naskh Arabic', serif"

    css_text = (
        "/* Basic RTL stylesheet for Arabic with embedded fonts */\n"
        + ("\n".join(font_faces) + ("\n" if font_faces else ""))
        + "html, body { direction: rtl; unicode-bidi: embed; }\n"
        + f"body {{ margin: 0; padding: 1rem; font-family: {body_fonts}; line-height: 1.9; font-size: 1rem; }}\n"
        + "h1,h2,h3,h4,h5,h6 { text-align: right; }\n"
        + ".chapter-title { margin: 0 0 1rem 0; font-size: 1.4rem; }\n"
        + ".chapter-body p { margin: 0 0 .8rem 0; text-align: justify; }\n"
    )
    css = css_text.encode("utf-8")

    # Chapters
    manifest_items = []
    spine_items = []
    nav_points = []

    text_files: List[Tuple[str, bytes]] = []
    # In minimal profile, do NOT include nav in spine (matches accepted sample)
    if not minimal_profile:
        spine_items = ["    <itemref idref=\"nav\"/>"]
    for idx, ch in enumerate(chapters, 1):
        fname = f"text/{idx:04d}_{make_slug(ch.title)}.xhtml"
        manifest_items.append(
            f"    <item id=\"ch{idx}\" href=\"{xsu.escape(fname)}\" media-type=\"application/xhtml+xml\"/>"
        )
        spine_items.append(f"    <itemref idref=\"ch{idx}\"/>")
        nav_points.append(
            f"      <li><a href=\"{xsu.escape(fname)}\">{xsu.escape(ch.title)}</a></li>"
        )
        text_files.append((fname, ch.xhtml.encode("utf-8")))

    if minimal_profile:
        nav_xhtml = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
            "<head><meta charset=\"utf-8\"/><title>الفهرس</title>\n"
            "<link rel=\"stylesheet\" type=\"text/css\" href=\"css/style.css\"/></head>\n"
            "<body><nav epub:type=\"toc\"><h2>الفهرس</h2><ol>\n%s\n"
            "</ol></nav></body></html>\n"
        ) % (meta.language, meta.language, "\n".join(nav_points))
    else:
        nav_xhtml = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
            "<head><meta charset=\"utf-8\"/><title>الفهرس</title>\n"
            "<link rel=\"stylesheet\" type=\"text/css\" href=\"css/style.css\"/></head>\n"
            "<body><nav epub:type=\"toc\"><h2>الفهرس</h2><ol>\n%s\n"
            "</ol></nav></body></html>\n"
        ) % (meta.language, meta.language, "\n".join(nav_points))

    # Font items in manifest
    font_manifest_xml = []
    for base, _data, _mime in locals().get('embed_fonts_payload', []) or []:
        font_manifest_xml.append(
            f"    <item id=\"font_{xsu.escape(base)}\" href=\"fonts/{xsu.escape(base)}\" media-type=\"{xsu.escape(_mime)}\"/>"
        )

    # Cover item in manifest (EPUB3 way)
    cover_manifest_xml = []
    if cover_asset:
        cover_name, _cover_bytes, cover_mime = cover_asset
        cover_manifest_xml.append(
            f"    <item id=\"cover-image\" href=\"images/{xsu.escape(cover_name)}\" media-type=\"{xsu.escape(cover_mime)}\" properties=\"cover-image\"/>"
        )

    # Optional extra metadata (hardened for minimal profile)
    if minimal_profile:
        dc_publisher = ""  # omit to avoid parser quirks
        creator_val = meta.author_page or meta.author or ""
        dc_creator = f"<dc:creator>{xsu.escape(creator_val)}</dc:creator>" if creator_val else ""
        dc_title = xsu.escape(meta.title)
    else:
        dc_publisher = f"    <dc:publisher>{xsu.escape(meta.publisher)}</dc:publisher>\n" if meta.publisher else ""
        dc_creator = f"<dc:creator>{xsu.escape(meta.author)}</dc:creator>" if meta.author else ""
        dc_title = xsu.escape(meta.book_title or meta.title)

    # Optional extra meta for Kindle (EPUB2-style cover hint)
    meta_cover_hint = "    <meta name=\"cover\" content=\"cover-image\"/>\n" if cover_asset else ""

    content_opf = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"book-id\" xml:lang=\"%s\">\n"
        "  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\">\n"
        "    <dc:identifier id=\"book-id\">%s</dc:identifier>\n"
        "    <dc:title>%s</dc:title>\n"
        "    <dc:language>%s</dc:language>\n"
        f"    {dc_publisher}"
        f"    {dc_creator}\n"
        f"{meta_cover_hint}"
        "    <meta property=\"dcterms:modified\">%s</meta>\n"
        "  </metadata>\n"
        "  <manifest>\n"
        "    <item id=\"nav\" href=\"nav.xhtml\" media-type=\"application/xhtml+xml\" properties=\"nav\"/>\n"
        "    <item id=\"css\" href=\"css/style.css\" media-type=\"text/css\"/>\n"
        "%s\n"
        "%s\n"
        "%s\n"
        "  </manifest>\n"
        "  <spine page-progression-direction=\"rtl\">\n"
        "%s\n"
        "  </spine>\n"
        "</package>\n"
    ) % (
        xsu.escape(meta.language),
        xsu.escape(book_id),
        dc_title,
        xsu.escape(meta.language),
        now,
        "\n".join(font_manifest_xml),
        "\n".join(cover_manifest_xml),
        "\n".join(manifest_items),
        "\n".join(spine_items),
    )

    # Write zip
    with zipfile.ZipFile(out_path, "w") as zf:
        # mimetype first, uncompressed
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, mimetype)
        # container
        zf.writestr("META-INF/container.xml", container_xml)
        # css
        zf.writestr("OEBPS/css/style.css", css)
        # nav and opf
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml.encode("utf-8"))
        zf.writestr("OEBPS/content.opf", content_opf.encode("utf-8"))
        # chapters
        for fname, data in text_files:
            zf.writestr(f"OEBPS/{fname}", data)
        # fonts
        for base, data, _mime in locals().get('embed_fonts_payload', []) or []:
            zf.writestr(f"OEBPS/fonts/{base}", data)
        # cover
        if cover_asset:
            cover_name, cover_bytes, _cover_mime = cover_asset
            zf.writestr(f"OEBPS/images/{cover_name}", cover_bytes)

def _image_urls_from_google(query: str, max_n: int = 8) -> List[str]:
    """Fetch Google Images HTML and extract up to max_n candidate image URLs.
    Heuristics only; no JS. Excludes gstatic icons.
    """
    url = f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}"
    try:
        req = Request(url, headers={
            "User-Agent": UA,
            "Accept-Language": "ar,en;q=0.8",
        })
        with contextlib.closing(urlopen(req, timeout=20)) as resp:
            html_data = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return []
    urls: List[str] = []
    # Primary: JSON field "ou":"<url>"
    for m in re.finditer(r'"ou":"(https?://[^\"]+)"', html_data):
        u = m.group(1)
        if 'gstatic.com' in u or 'google.' in urlparse(u).hostname or 'logo' in u:
            continue
        urls.append(u)
        if len(urls) >= max_n:
            break
    # Fallback: direct jpg/png links
    if not urls:
        for m in re.finditer(r'(https?://[^\"\s>]+\.(?:jpg|jpeg|png))', html_data, flags=re.I):
            u = m.group(1)
            if 'gstatic.com' in u or 'google.' in urlparse(u).hostname or 'logo' in u:
                continue
            urls.append(u)
            if len(urls) >= max_n:
                break
    return urls


def _download_bytes(url: str) -> Optional[Tuple[bytes, str]]:
    try:
        req = Request(url, headers={"User-Agent": UA, "Referer": "https://www.google.com/"})
        with contextlib.closing(urlopen(req, timeout=30)) as resp:
            data = resp.read()
            ctype = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
            return data, ctype
    except Exception:
        return None


def _image_size(data: bytes) -> Optional[Tuple[int, int]]:
    """Return (width, height) for PNG/JPEG if detectable; else None."""
    # PNG signature
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        # IHDR chunk: 8(sig)+4(len)+4('IHDR') then 13 bytes
        if len(data) >= 33 and data[12:16] == b'IHDR':
            w = int.from_bytes(data[16:20], 'big')
            h = int.from_bytes(data[20:24], 'big')
            return w, h
        return None
    # JPEG: parse markers for SOF0/2
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data)-1:
            if data[i] != 0xFF:
                i += 1
                continue
            # skip padding FFs
            while i < len(data) and data[i] == 0xFF:
                i += 1
            if i >= len(data):
                break
            marker = data[i]
            i += 1
            # markers without length
            if marker in (0xD8, 0xD9):
                continue
            if i+1 >= len(data):
                break
            seg_len = int.from_bytes(data[i:i+2], 'big')
            if seg_len < 2 or i+seg_len > len(data):
                break
            if marker in (0xC0, 0xC2):  # SOF0/2
                if i+7 < len(data):
                    # [len(2)] [precision(1)] [height(2)] [width(2)]
                    h = int.from_bytes(data[i+3:i+5], 'big')
                    w = int.from_bytes(data[i+5:i+7], 'big')
                    return w, h
            i += seg_len
    return None


def build_chapter_xhtml2(title: str, body_html: str, lang: str = "ar") -> str:
    title_xml = xsu.escape(title)
    doctype = (
        "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.1//EN\" \n"
        "  \"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd\">\n"
    )
    return (
        doctype
        + "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
        + "<head>\n"
        + "  <meta http-equiv=\"Content-Type\" content=\"application/xhtml+xml; charset=utf-8\"/>\n"
        + "  <title>%s</title>\n"
        + "  <link rel=\"stylesheet\" type=\"text/css\" href=\"../css/style.css\"/>\n"
        + "</head>\n"
        + "<body>\n"
        + "  <h1 class=\"chapter-title\">%s</h1>\n"
        + "  <div class=\"chapter-body\">%s</div>\n"
        + "</body>\n"
        + "</html>\n"
    ) % (lang, lang, title_xml, title_xml, body_html)


def build_cover_xhtml2(meta: BookMeta) -> str:
    title = xsu.escape(meta.book_title or meta.title)
    author = xsu.escape(meta.author or "")
    body = (
        f"<div class=\"cover-wrap\">"
        f"<h1 class=\"cover-title\">{title}</h1>"
        f"<div class=\"cover-author\">{author}</div>"
        f"</div>"
    )
    css_extra = (
        ".cover-wrap{display:flex;flex-direction:column;justify-content:center;align-items:flex-end;"
        "min-height:90vh;padding:2rem 1rem;gap:1rem;}"
        ".cover-title{font-size:2rem;line-height:1.4;margin:0;text-align:right;}"
        ".cover-author{font-size:1.2rem;color:#444;}"
    )
    doctype = (
        "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.1//EN\" \n"
        "  \"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd\">\n"
    )
    return (
        doctype
        + "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
        + "<head>\n"
        + "  <meta http-equiv=\"Content-Type\" content=\"application/xhtml+xml; charset=utf-8\"/>\n"
        + "  <title>%s</title>\n"
        + "  <link rel=\"stylesheet\" type=\"text/css\" href=\"../css/style.css\"/>\n"
        + f"  <style>{css_extra}</style>\n"
        + "</head>\n"
        + "<body>\n%s\n"
        + "</body>\n"
        + "</html>\n"
    ) % (meta.language, meta.language, title, body)


def build_info_xhtml2(meta: BookMeta) -> str:
    def row(label: str, value: Optional[str]) -> str:
        if not value:
            return ""
        return f"<p><strong>{xsu.escape(label)}:</strong> {xsu.escape(value)}</p>"

    content = (
        row("الكتاب", meta.book_title or meta.title)
        + row("المؤلف", meta.author)
        + row("الناشر", meta.publisher)
        + row("الطبعة", meta.edition)
        + row("عدد الصفحات", meta.pages)
        + (f"<p><strong>صفحة المؤلف:</strong> {xsu.escape(meta.author_page)}" + "</p>" if meta.author_page else "")
    )
    body = f"<section><h1>بطاقة الكتاب</h1>{content}</section>"
    return build_chapter_xhtml2("بطاقة الكتاب", body, lang=meta.language)


def write_epub2(meta: BookMeta, chapters: List[Chapter], out_path: str, *, font_files: Optional[List[str]] = None):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    book_id = meta.identifier

    mimetype = b"application/epub+zip"
    container_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">\n"
        "  <rootfiles>\n"
        "    <rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/>\n"
        "  </rootfiles>\n"
        "</container>\n"
    ).encode("utf-8")

    # Fonts
    font_faces: List[str] = []
    embed_fonts_payload = []
    font_families_order: List[str] = []
    for fpath in (font_files or []):
        try:
            with open(fpath, 'rb') as fh:
                data = fh.read()
        except OSError:
            continue
        base = os.path.basename(fpath)
        family, weight, style = _guess_font_meta(base)
        if family not in font_families_order:
            font_families_order.append(family)
        src_url = f"../fonts/{base}"
        fmt = os.path.splitext(base)[1].lower().lstrip('.')
        if fmt == 'ttf':
            fmt_str = "format('truetype')"
        elif fmt == 'otf':
            fmt_str = "format('opentype')"
        elif fmt == 'woff':
            fmt_str = "format('woff')"
        elif fmt == 'woff2':
            fmt_str = "format('woff2')"
        else:
            fmt_str = ""
        font_faces.append(
            "@font-face { font-family: '" + xsu.escape(family) + "'; src: url('" + xsu.escape(src_url) + "') " + fmt_str + "; font-weight: " + weight + "; font-style: " + style + "; font-display: swap; }"
        )
        embed_fonts_payload.append((base, data, _font_mime(base)))

    body_fonts = ", ".join([f"'{xsu.escape(f)}'" for f in font_families_order] + ["'Amiri'", "'Noto Naskh Arabic'", "serif"]) or "'Amiri', 'Noto Naskh Arabic', serif"

    css_text = (
        "/* EPUB2 RTL stylesheet for Arabic with embedded fonts */\n"
        + ("\n".join(font_faces) + ("\n" if font_faces else ""))
        + "html, body { direction: rtl; unicode-bidi: embed; }\n"
        + f"body {{ margin: 0; padding: 1rem; font-family: {body_fonts}; line-height: 1.9; font-size: 1rem; }}\n"
        + "h1,h2,h3,h4,h5,h6 { text-align: right; }\n"
        + ".chapter-title { margin: 0 0 1rem 0; font-size: 1.4rem; }\n"
        + ".chapter-body p { margin: 0 0 .8rem 0; text-align: justify; }\n"
    )
    css = css_text.encode("utf-8")

    # Manifest & spine
    manifest_items = []
    spine_items = []
    text_files: List[Tuple[str, bytes]] = []
    nav_points = []

    for idx, ch in enumerate(chapters, 1):
        fname = f"text/{idx:04d}_{make_slug(ch.title)}.xhtml"
        manifest_items.append(
            f"    <item id=\"ch{idx}\" href=\"{xsu.escape(fname)}\" media-type=\"application/xhtml+xml\"/>"
        )
        spine_items.append(f"    <itemref idref=\"ch{idx}\"/>")
        nav_points.append(
            f"    <navPoint id=\"np{idx}\" playOrder=\"{idx}\">\n      <navLabel><text>{xsu.escape(ch.title)}</text></navLabel>\n      <content src=\"{xsu.escape(fname)}\"/>\n    </navPoint>"
        )
        text_files.append((fname, ch.xhtml.encode("utf-8")))

    # Build toc.ncx
    ncx = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<ncx xmlns=\"http://www.daisy.org/z3986/2005/ncx/\" version=\"2005-1\">\n"
        "  <head>\n"
        "    <meta name=\"dtb:uid\" content=\"%s\"/>\n"
        "    <meta name=\"dtb:depth\" content=\"1\"/>\n"
        "    <meta name=\"dtb:totalPageCount\" content=\"0\"/>\n"
        "    <meta name=\"dtb:maxPageNumber\" content=\"0\"/>\n"
        "  </head>\n"
        "  <docTitle><text>%s</text></docTitle>\n"
        "  <navMap>\n%s\n"
        "  </navMap>\n"
        "</ncx>\n"
    ) % (xsu.escape(book_id), xsu.escape(meta.book_title or meta.title), "\n".join(nav_points))

    # OPF 2.0
    dc_publisher = f"    <dc:publisher>{xsu.escape(meta.publisher)}</dc:publisher>\n" if meta.publisher else ""
    dc_creator = f"    <dc:creator opf:role=\"aut\">{xsu.escape(meta.author)}</dc:creator>\n" if meta.author else ""
    dc_title = xsu.escape(meta.book_title or meta.title)
    opf = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<package xmlns=\"http://www.idpf.org/2007/opf\" unique-identifier=\"book-id\" version=\"2.0\">\n"
        "  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:opf=\"http://www.idpf.org/2007/opf\">\n"
        "    <dc:identifier id=\"book-id\">%s</dc:identifier>\n"
        "    <dc:title>%s</dc:title>\n"
        "    <dc:language>%s</dc:language>\n"
        f"{dc_publisher}"
        f"{dc_creator}"
        "    <meta name=\"cover\" content=\"ch1\"/>\n"
        "  </metadata>\n"
        "  <manifest>\n"
        "    <item id=\"ncx\" href=\"toc.ncx\" media-type=\"application/x-dtbncx+xml\"/>\n"
        "    <item id=\"css\" href=\"css/style.css\" media-type=\"text/css\"/>\n"
        "%s\n"
        "  </manifest>\n"
        "  <spine toc=\"ncx\">\n"
        "%s\n"
        "  </spine>\n"
        "</package>\n"
    ) % (
        xsu.escape(book_id),
        dc_title,
        xsu.escape(meta.language),
        "\n".join(manifest_items),
        "\n".join(spine_items),
    )

    with zipfile.ZipFile(out_path, "w") as zf:
        # mimetype uncompressed first
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, mimetype)
        # container
        zf.writestr("META-INF/container.xml", container_xml)
        # css
        zf.writestr("OEBPS/css/style.css", css)
        # ncx and opf
        zf.writestr("OEBPS/toc.ncx", ncx.encode("utf-8"))
        zf.writestr("OEBPS/content.opf", opf.encode("utf-8"))
        # chapters
        for fname, data in text_files:
            zf.writestr(f"OEBPS/{fname}", data)
        # fonts
        for base, data, _mime in embed_fonts_payload:
            zf.writestr(f"OEBPS/fonts/{base}", data)


# -----------------------------
# Orchestration
# -----------------------------


def _split_chapters(chapters: List[Chapter], per_file: int) -> List[List[Chapter]]:
    if per_file <= 0:
        return [chapters]
    # Keep first two (cover, info) in every split
    head = [c for c in chapters if c.order in (0, 1)]
    rest = [c for c in chapters if c.order not in (0, 1)]
    chunks: List[List[Chapter]] = []
    for i in range(0, len(rest), per_file):
        block = head + rest[i:i+per_file]
        # Reassign order within each split
        for j, ch in enumerate(block):
            ch.order = j
        chunks.append(block)
    return chunks or [chapters]


def scrape_book_to_epub(book_url: str, out_path: Optional[str] = None, throttle: float = 0.8, limit: Optional[int] = None, *, cover_auto: bool = False):
    if not re.search(r"https?://[\w.:-]+/book/\d+/?$", book_url):
        # Allow urls with trailing slash omitted
        book_url = re.sub(r"/+$", "", book_url)
    print(f"[+] Fetch book page: {book_url}")
    index_html = fetch(book_url)

    meta = parse_book_meta(index_html)
    toc = parse_toc(book_url, index_html)
    print(f"[+] TOC entries: {len(toc)}")

    chapters: List[Chapter] = []
    # Минимальный профиль: без обложки и карточки
    for i, item in enumerate(toc, 1):
        if limit is not None and i > limit:
            break
        print(f"  - [{i:03d}/{len(toc)}] Fetch chapter id={item.id} …", end="", flush=True)
        html_text = fetch(item.url, referer=book_url)
        title = extract_title_from_page(html_text) or item.title
        cp = ContentParser()
        cp.feed(html_text)
        body_html = cp.get_content()
        if not body_html:
            # Fallback: try to grab main content heuristically by removing side nav
            cleaned = re.sub(r"<div[^>]*class=\"s-nav\"[\s\S]*?</div>", "", html_text)
            m = re.search(r'<div[^>]*class="nass[^"]*"[^>]*>([\s\S]*?)</div>', cleaned)
            body_html = m.group(1) if m else ""
            body_html = html.unescape(body_html)
        xhtml = build_chapter_xhtml_min(title, body_html)
        chapters.append(Chapter(id=item.id, order=item.order + 2, title=title, xhtml=xhtml))
        print(" done.")
        time.sleep(throttle)

    # Output path (default: book title)
    if not out_path:
        fname = make_title_filename(meta.title) + ".epub"
        out_path = os.path.join("output", fname)

    # Optional cover auto-fetch
    cover_asset = None
    if cover_auto:
        q_candidates = [
            f"{meta.book_title or meta.title} cover",
            f"{meta.book_title or meta.title} book cover",
            f"{meta.book_title or meta.title} غلاف",
        ]
        img_url = None
        for q in q_candidates:
            for cand in _image_urls_from_google(q, max_n=8):
                got = _download_bytes(cand)
                if not got:
                    continue
                data, ctype = got
                # Accept only JPEG/PNG
                if ctype not in ("image/jpeg", "image/jpg", "image/png"):
                    continue
                size = _image_size(data)
                if not size:
                    continue
                w, h = size
                # Heuristics: require reasonable dimensions and size
                if min(w, h) < 300 or len(data) < 50 * 1024:
                    continue
                ext = 'png' if ('png' in ctype or cand.lower().endswith('.png')) else 'jpg'
                cover_name = f"cover.{ext}"
                cover_mime = 'image/png' if ext == 'png' else 'image/jpeg'
                cover_asset = (cover_name, data, cover_mime)
                img_url = cand
                break
            if img_url:
                print(f"[+] Cover image fetched: {img_url}")
                break
        if not img_url:
            print("[!] No suitable cover image found (size filter)")

    print(f"[+] Writing EPUB: {out_path}")
    write_epub3(meta, chapters, out_path, minimal_profile=True, cover_asset=cover_asset)
    print("[✓] Done.")


# -----------------------------
# DOCX writer (Kindle-friendly via Send-to-Kindle)
# -----------------------------


def _html_to_text_paragraphs(html_in: str) -> List[str]:
    # Replace <br> with newline
    s = re.sub(r"<br\s*/?>", "\n", html_in, flags=re.I)
    # Block endings to newline
    s = re.sub(r"</(p|div|li|h\d|blockquote)>", "\n", s, flags=re.I)
    # Remove all tags
    s = re.sub(r"<[^>]+>", "", s)
    # Unescape
    s = html.unescape(s)
    # Normalize whitespace
    lines = [line.strip() for line in s.splitlines()]
    paras: List[str] = []
    buf: List[str] = []
    for ln in lines:
        if not ln:
            if buf:
                paras.append(" ".join(buf).strip())
                buf = []
        else:
            buf.append(ln)
    if buf:
        paras.append(" ".join(buf).strip())
    return [p for p in paras if p]


def _docx_xml_escape(s: str) -> str:
    return xsu.escape(s)


def write_docx(meta: BookMeta, chapters: List[Chapter], out_path: str):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    # Core parts
    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">\n"
        "  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>\n"
        "  <Default Extension=\"xml\" ContentType=\"application/xml\"/>\n"
        "  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>\n"
        "  <Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>\n"
        "  <Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>\n"
        "</Types>\n"
    )

    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\n"
        "  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>\n"
        "  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>\n"
        "</Relationships>\n"
    )

    title = meta.book_title or meta.title
    author = meta.author or ""
    core = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">\n"
        f"  <dc:title>{_docx_xml_escape(title)}</dc:title>\n"
        f"  <dc:creator>{_docx_xml_escape(author)}</dc:creator>\n"
        f"  <dc:language>{_docx_xml_escape(meta.language)}</dc:language>\n"
        "</cp:coreProperties>\n"
    )

    styles = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n"
        "  <w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\">\n"
        "    <w:name w:val=\"Normal\"/>\n"
        "    <w:qFormat/>\n"
        "    <w:pPr><w:bidi w:val=\"1\"/><w:jc w:val=\"right\"/></w:pPr>\n"
        "  </w:style>\n"
        "  <w:style w:type=\"paragraph\" w:styleId=\"Heading1\">\n"
        "    <w:name w:val=\"heading 1\"/>\n"
        "    <w:basedOn w:val=\"Normal\"/>\n"
        "    <w:next w:val=\"Normal\"/>\n"
        "    <w:qFormat/>\n"
        "    <w:pPr><w:bidi w:val=\"1\"/><w:jc w:val=\"right\"/></w:pPr>\n"
        "    <w:rPr><w:b w:val=\"1\"/><w:sz w:val=\"32\"/></w:rPr>\n"
        "  </w:style>\n"
        "</w:styles>\n"
    )

    def p_xml(text: str, style: Optional[str] = None) -> str:
        t = _docx_xml_escape(text)
        style_xml = f"<w:pStyle w:val=\"{style}\"/>" if style else ""
        return (
            "<w:p xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
            f"<w:pPr><w:bidi w:val=\"1\"/>{style_xml}</w:pPr>"
            f"<w:r><w:t xml:space=\"preserve\">{t}</w:t></w:r>"
            "</w:p>"
        )

    # Build document
    doc_parts: List[str] = []
    # Cover
    doc_parts.append(p_xml(title, style="Heading1"))
    if author:
        doc_parts.append(p_xml(author))
    doc_parts.append(p_xml(""))
    # Info page
    info_lines = []
    info_lines.append(f"الكتاب: {title}")
    if meta.author:
        info_lines.append(f"المؤلف: {meta.author}")
    if meta.publisher:
        info_lines.append(f"الناشر: {meta.publisher}")
    if meta.edition:
        info_lines.append(f"الطبعة: {meta.edition}")
    if meta.pages:
        info_lines.append(f"عدد الصفحات: {meta.pages}")
    if meta.author_page:
        info_lines.append(f"صفحة المؤلف: {meta.author_page}")
    doc_parts.append(p_xml("بطاقة الكتاب", style="Heading1"))
    for line in info_lines:
        doc_parts.append(p_xml(line))
    doc_parts.append(p_xml(""))
    # Chapters
    for ch in chapters:
        # Skip if our inserted cover/info (already added)
        if ch.order in (0, 1):
            continue
        doc_parts.append(p_xml(ch.title, style="Heading1"))
        # Extract body text
        m = re.search(r"<div[^>]*class=\"chapter-body\"[^>]*>([\s\S]*?)</div>", ch.xhtml)
        body = m.group(1) if m else ch.xhtml
        for para in _html_to_text_paragraphs(body):
            doc_parts.append(p_xml(para))

    document = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n"
        "  <w:body>\n"
        + "\n".join(doc_parts)
        + "\n    <w:sectPr xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:rtlGutter/></w:sectPr>\n"
        + "  </w:body>\n"
        + "</w:document>\n"
    )

    with zipfile.ZipFile(out_path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("docProps/core.xml", core)
        zf.writestr("word/styles.xml", styles)
        zf.writestr("word/document.xml", document)


def scrape_book_to_docx(book_url: str, out_path: Optional[str] = None, throttle: float = 0.8, limit: Optional[int] = None):
    if not re.search(r"https?://[\w.:-]+/book/\d+/?$", book_url):
        book_url = re.sub(r"/+$", "", book_url)
    print(f"[+] Fetch book page: {book_url}")
    index_html = fetch(book_url)
    meta = parse_book_meta(index_html)
    toc = parse_toc(book_url, index_html)
    print(f"[+] TOC entries: {len(toc)}")

    chapters: List[Chapter] = []
    # Insert cover and info as chapters 0,1
    cover_xhtml = build_cover_xhtml2(meta)
    chapters.append(Chapter(id=0, order=0, title=meta.book_title or meta.title, xhtml=cover_xhtml))
    info_xhtml = build_info_xhtml2(meta)
    chapters.append(Chapter(id=0, order=1, title="بطاقة الكتاب", xhtml=info_xhtml))

    for i, item in enumerate(toc, 1):
        if limit is not None and i > limit:
            break
        print(f"  - [{i:03d}/{len(toc)}] Fetch chapter id={item.id} …", end="", flush=True)
        html_text = fetch(item.url, referer=book_url)
        title = extract_title_from_page(html_text) or item.title
        cp = ContentParser(); cp.feed(html_text)
        body_html = cp.get_content()
        if not body_html:
            cleaned = re.sub(r"<div[^>]*class=\"s-nav\"[\s\S]*?</div>", "", html_text)
            m = re.search(r'<div[^>]*class="nass[^"]*"[^>]*>([\s\S]*?)</div>', cleaned)
            body_html = m.group(1) if m else ""
            body_html = html.unescape(body_html)
        xhtml = build_chapter_xhtml2(title, body_html)
        chapters.append(Chapter(id=item.id, order=item.order + 2, title=title, xhtml=xhtml))
        print(" done.")
        time.sleep(throttle)

    if not out_path:
        fname = make_title_filename(meta.title) + ".docx"
        out_path = os.path.join("output", fname)

    print(f"[+] Writing DOCX: {out_path}")
    write_docx(meta, chapters, out_path)
    print("[✓] Done.")


    print("[✓] Done.")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Download a Shamela book and build minimal EPUB3 (RTL, Kindle-friendly)")
    ap.add_argument("url", help="Book URL like https://shamela.ws/book/158")
    ap.add_argument("-o", "--output", help="Output EPUB path (default: output/<book title>.epub)")
    ap.add_argument("--throttle", type=float, default=0.8, help="Delay between requests in seconds")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of chapters for a quick run")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--cover-auto", action="store_true", help="Fetch Google Images result as cover (best-effort)")
    group.add_argument("--cover", help="Path to local cover image (jpg/png)")
    args = ap.parse_args(argv)

    try:
        # Determine output path
        if not args.output:
            index_html = fetch(args.url)
            meta = parse_book_meta(index_html)
            title = strip_book_prefix(meta.book_title or meta.title)
            if meta.publisher:
                combo = f"{title} - {meta.publisher}"
            else:
                combo = title
            base_name = make_title_filename(combo)
            args.output = os.path.join('output', base_name + '.epub')

        # If local cover provided, we'll inject it inside scrape
        if args.cover:
            # Read and validate cover; then pass via temp flag by monkey-patching helper
            path = args.cover
            try:
                with open(path, 'rb') as fh:
                    data = fh.read()
                size = _image_size(data)
                if not size or min(size) < 300:
                    print("[!] Local cover too small or unreadable; proceeding without cover", file=sys.stderr)
                    return scrape_book_to_epub(args.url, args.output, throttle=args.throttle, limit=args.limit, cover_auto=False)
                ext = os.path.splitext(path)[1].lower()
                cover_mime = 'image/png' if ext == '.png' else 'image/jpeg'
                # Inject via wrapper: we call lower-level writer after scrape
                # Simpler: temporarily write a small wrapper around scrape
            except Exception as e:
                print(f"[!] Failed to read cover file: {e}", file=sys.stderr)
                return scrape_book_to_epub(args.url, args.output, throttle=args.throttle, limit=args.limit, cover_auto=False)

            # Scrape content without auto cover, then rebuild with cover
            # We'll duplicate minimal part: fetch index + toc + chapters
            if not re.search(r"https?://[\w.:-]+/book/\d+/?$", args.url):
                book_url = re.sub(r"/+$", "", args.url)
            else:
                book_url = args.url
            print(f"[+] Fetch book page: {book_url}")
            index_html = fetch(book_url)
            meta = parse_book_meta(index_html)
            toc = parse_toc(book_url, index_html)
            print(f"[+] TOC entries: {len(toc)}")
            chapters: List[Chapter] = []
            for i, item in enumerate(toc, 1):
                if args.limit is not None and i > args.limit:
                    break
                print(f"  - [{i:03d}/{len(toc)}] Fetch chapter id={item.id} …", end="", flush=True)
                html_text = fetch(item.url, referer=book_url)
                title = extract_title_from_page(html_text) or item.title
                cp = ContentParser(); cp.feed(html_text)
                body_html = cp.get_content()
                if not body_html:
                    cleaned = re.sub(r"<div[^>]*class=\"s-nav\"[\s\S]*?</div>", "", html_text)
                    m = re.search(r'<div[^>]*class="nass[^"]*"[^>]*>([\s\S]*?)</div>', cleaned)
                    body_html = m.group(1) if m else ""
                    body_html = html.unescape(body_html)
                xhtml = build_chapter_xhtml_min(title, body_html)
                chapters.append(Chapter(id=item.id, order=item.order + 2, title=title, xhtml=xhtml))
                print(" done.")
                time.sleep(args.throttle)

            print(f"[+] Writing EPUB: {args.output}")
            cover_name = 'cover.png' if cover_mime == 'image/png' else 'cover.jpg'
            write_epub3(meta, chapters, args.output, minimal_profile=True, cover_asset=(cover_name, data, cover_mime))
            print("[✓] Done.")
            return 0

        scrape_book_to_epub(args.url, args.output, throttle=args.throttle, limit=args.limit, cover_auto=bool(args.cover_auto))
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"[!] Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
