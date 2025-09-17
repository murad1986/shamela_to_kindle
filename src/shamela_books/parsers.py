from __future__ import annotations

import html
import io
import re
import xml.sax.saxutils as xsu
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from .models import BookMeta, TocItem
from .utils import norm_ar_text


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

