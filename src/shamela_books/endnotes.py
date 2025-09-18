from __future__ import annotations

import html
import re
import xml.sax.saxutils as xsu
from typing import Tuple, Optional

from .utils import ar_digits_to_ascii


_RE_HAMESH = re.compile(r"(?:<hr[^>]*>\s*)?<p[^>]*class=\"[^\"]*\bhamesh\b[^\"]*\"[^>]*>([\s\S]*?)</p>", re.I)
_RE_BR = re.compile(r"<br\s*/?>", re.I)
_RE_NUM_LINE_PAREN = re.compile(r"^\s*\(\s*([0-9\u0660-\u0669]+)\s*\)\s*(.+)$")
_RE_NUM_LINE_SEP = re.compile(r"^\s*([0-9\u0660-\u0669]+)\s*[\.\-–—:\)]\s*(.+)$")
_RE_TAGS = re.compile(r"<[^>]+>")
_RE_REF_PAREN = re.compile(r"\(\s*([0-9\u0660-\u0669]+)\s*\)")
_RE_REF_BRACK = re.compile(r"\[\s*([0-9\u0660-\u0669]+)\s*\]")


def extract_endnotes(body_html: str) -> tuple[str, list[tuple[str, str]]]:
    """Extract endnotes from one or more <p class="hamesh"> blocks.
    Returns (body_without_hamesh, notes) where notes is list of (num_ascii, text),
    deduplicated by numeric key, preserving first occurrence.
    """
    notes_map: dict[str, str] = {}
    last_end = 0
    out_parts: list[str] = []
    for m in _RE_HAMESH.finditer(body_html):
        # Keep content before this hamesh block
        out_parts.append(body_html[last_end:m.start()])
        inner = m.group(1)
        parts = _RE_BR.split(inner)
        current_num: Optional[str] = None
        current_text_parts: list[str] = []

        def flush():
            nonlocal current_num, current_text_parts
            if current_num is not None:
                text = " ".join(t for t in current_text_parts if t).strip()
                if current_num not in notes_map and text:
                    notes_map[current_num] = text
            current_num = None
            current_text_parts = []

        for raw in parts:
            line = html.unescape(_RE_TAGS.sub("", raw)).strip()
            if not line:
                continue
            mm = _RE_NUM_LINE_PAREN.match(line) or _RE_NUM_LINE_SEP.match(line)
            if mm:
                flush()
                num_ascii = ar_digits_to_ascii(mm.group(1))
                txt = mm.group(2).strip()
                current_num = num_ascii
                current_text_parts = [txt]
            else:
                if current_num is not None:
                    current_text_parts.append(line)
        flush()
        last_end = m.end()
    # Append remainder after last hamesh (or whole body if none)
    out_parts.append(body_html[last_end:])
    body_wo = "".join(out_parts)
    notes = [(k, v) for k, v in notes_map.items()]
    # Keep numeric order if possible
    try:
        notes.sort(key=lambda kv: int(kv[0]))
    except Exception:
        pass
    return body_wo, notes


def link_endnote_refs(body_html: str, num_map: dict[str, int]) -> str:
    """Replace (N) markers in text with sup/anchor links to global notes."""

    def repl_paren(match: re.Match) -> str:
        disp = match.group(0)  # e.g., (١)
        num_disp = match.group(1)
        num_ascii = ar_digits_to_ascii(num_disp)
        if num_ascii not in num_map:
            return disp
        gid = num_map[num_ascii]
        return f"<sup><a id=\"ref-{gid}\" href=\"endnotes.xhtml#note-{gid}\">{gid}</a></sup>"

    # First, normalize existing <sup><a>…</a></sup>
    def repl_sup_a(m: re.Match) -> str:
        inner = m.group(1).strip()
        # extract the visible number (allow parentheses)
        if inner.startswith("(") and inner.endswith(")"):
            num_disp = inner[1:-1].strip()
            disp = inner
        else:
            num_disp = inner
            disp = inner
        num_ascii = ar_digits_to_ascii(num_disp)
        if num_ascii not in num_map:
            return m.group(0)
        gid = num_map[num_ascii]
        return f"<sup><a id=\"ref-{gid}\" href=\"endnotes.xhtml#note-{gid}\">{gid}</a></sup>"

    out = re.sub(r"<sup[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</sup>", repl_sup_a, body_html, flags=re.I)

    # Then, link bare <sup>١</sup> or <sup>(١)</sup>
    def repl_sup(m: re.Match) -> str:
        inside = m.group(1)
        if '<a ' in inside or 'href=' in inside:
            return m.group(0)
        inner = inside.strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner_num = inner[1:-1].strip()
            disp = inner_num
        else:
            inner_num = inner
            disp = inner
        num_ascii = ar_digits_to_ascii(inner_num)
        if num_ascii not in num_map:
            return m.group(0)
        gid = num_map[num_ascii]
        return f"<sup><a id=\"ref-{gid}\" href=\"endnotes.xhtml#note-{gid}\">{gid}</a></sup>"

    out = re.sub(r"<sup>\s*([^<]+?)\s*</sup>", repl_sup, out, flags=re.I)

    # Finally, link remaining (N) markers in plain text (outside <sup>..</sup>)
    out = _RE_REF_PAREN.sub(repl_paren, out)
    # And [N] markers
    def repl_brack(match: re.Match) -> str:
        disp = match.group(0)
        num_disp = match.group(1)
        num_ascii = ar_digits_to_ascii(num_disp)
        if num_ascii not in num_map:
            return disp
        gid = num_map[num_ascii]
        return f"<sup><a id=\"ref-{gid}\" href=\"endnotes.xhtml#note-{gid}\">{gid}</a></sup>"
    out = _RE_REF_BRACK.sub(repl_brack, out)
    return out


def build_endnotes_xhtml(lang: str, entries: list[tuple[int, str]]) -> str:
    items = []
    for gid, text in entries:
        # Best-effort: strip duplicated leading number patterns like "232 - " or "(232)"
        t = text.lstrip()
        patts = [
            f"{gid}.", f"{gid}-", f"{gid} –", f"{gid} —", f"{gid}:", f"({gid})", f"{gid})",
        ]
        for p in patts:
            if t.startswith(p):
                t = t[len(p):].lstrip()
                break
        t_xml = xsu.escape(t)
        items.append(
            f"<li id=\"note-{gid}\"><span class=\"note-num\">{gid}.</span> {t_xml} <a href=\"#ref-{gid}\">↩︎</a></li>"
        )
    ol = "\n".join(items)
    title = "الهوامش"
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\"/>\n"
        "  <title>%s</title>\n"
        "  <link rel=\"stylesheet\" type=\"text/css\" href=\"../css/style.css\"/>\n"
        "</head>\n"
        "<body>\n"
        "  <section epub:type=\"backmatter endnotes\">\n"
        "    <h1 class=\"chapter-title\">%s</h1>\n"
        "    <ol class=\"endnotes\">%s</ol>\n"
        "  </section>\n"
        "</body>\n"
        "</html>\n"
    ) % (lang, lang, xsu.escape(title), xsu.escape(title), ol)
