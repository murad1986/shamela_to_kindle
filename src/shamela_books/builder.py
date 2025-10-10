from __future__ import annotations

import os
import re
import xml.sax.saxutils as xsu
import zipfile
from typing import List, Optional, Tuple, Dict

from .models import BookMeta, Chapter
from .utils import norm_ar_text
from .utils import BIDI_CTRL


def build_chapter_xhtml_min(title: str, body_html: str, lang: str = "ar") -> str:
    """Minimal EPUB3 XHTML (matches Kindle-accepted sample)."""
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


def make_slug(s: str) -> str:
    s = re.sub(r"[\s\u200f\u200e\u202a-\u202e]+", "-", s.strip())
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.U)
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "chapter"


def make_title_filename(title: str) -> str:
    """Make a safe filename from book title, preserving Arabic letters."""
    t = norm_ar_text(title)
    t = (
        t.replace('/', '-').replace('\\', '-').replace(':', ' - ')
        .replace('*', ' ').replace('?', ' ').replace('"', "'")
        .replace('<', '(').replace('>', ')').replace('|', '-')
        .strip()
    )
    t = re.sub(r"\s+", " ", t)
    if len(t) > 120:
        t = t[:120].rstrip()
    return t or 'book'


def strip_book_prefix(title: str) -> str:
    """Remove leading Arabic 'كتاب'/'الكتاب' tokens from a title for filenames."""
    s = norm_ar_text(title)
    s = re.sub(r'^\s*(?:ال)?كتاب\s*[:\-–—]?\s*', '', s)
    return s.strip() or title


def _guess_font_meta(filename: str) -> tuple[str, str, str]:
    base = os.path.basename(filename)
    name, _ext = os.path.splitext(base)
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


def write_epub3(
    meta: BookMeta,
    chapters: List[Chapter],
    out_path: str,
    *,
    font_files: Optional[List[str]] = None,
    minimal_profile: bool = False,
    cover_asset: Optional[Tuple[str, bytes, str]] = None,
    endnotes_entries: Optional[List[Tuple[int, str]]] = None,
    endnote_gid_to_chapter_id: Optional[Dict[int, int]] = None,
    inline_images: Optional[List[Tuple[str, bytes, str]]] = None,
    subnav_by_chapter: Optional[Dict[int, List[Tuple[str, str]]]] = None,
    endnote_gid_to_section_id: Optional[Dict[int, str]] = None,
):
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

    font_faces: List[str] = []
    manifest_fonts: List[str] = []
    font_families_order: List[str] = []
    font_files = font_files or []
    embed_fonts_payload: List[Tuple[str, bytes, str]] = []
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
        embed_fonts_payload.append((base, data, _font_mime(base)))

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

    manifest_items = []
    spine_items = []
    toc_entries: List[Dict[str, object]] = []

    # Sort chapters by their order to stabilize filenames
    chapters_sorted = sorted(chapters, key=lambda c: c.order)

    text_files: List[Tuple[str, bytes]] = []
    chid_to_fname: Dict[int, str] = {}

    for idx, ch in enumerate(chapters_sorted, 1):
        fname = f"text/{idx:04d}.xhtml"
        manifest_items.append(
            f"    <item id=\"ch{idx}\" href=\"{xsu.escape(fname)}\" media-type=\"application/xhtml+xml\"/>"
        )
        spine_items.append(f"    <itemref idref=\"ch{idx}\"/>")
        children = (subnav_by_chapter or {}).get(ch.id, [])
        child_entries = [
            {
                "title": atitle,
                "href": f"{fname}#{aid}",
                "children": [],
            }
            for aid, atitle in children
        ]
        toc_entries.append(
            {
                "title": ch.title,
                "href": fname,
                "children": child_entries,
            }
        )
        text_files.append((fname, ch.xhtml.encode("utf-8")))
        chid_to_fname[ch.id] = fname.replace("text/", "")

    # Append endnotes page last if provided
    if endnotes_entries:
        end_fname = "text/endnotes.xhtml"
        manifest_items.append(
            f"    <item id=\"endnotes\" href=\"{xsu.escape(end_fname)}\" media-type=\"application/xhtml+xml\"/>"
        )
        spine_items.append("    <itemref idref=\"endnotes\"/>")
        # Build endnotes XHTML with per-note backlinks to chapter filenames
        items_xml = []
        gid_to_ch = endnote_gid_to_chapter_id or {}
        gid_to_sec = endnote_gid_to_section_id or {}
        # Build map from chapter id -> anchor id -> title for lookup
        sec_title: Dict[str, str] = {}
        if subnav_by_chapter:
            for ch_id, lst in subnav_by_chapter.items():
                for aid, at in lst:
                    sec_title[f"{ch_id}:{aid}"] = at
        import re as _re
        for gid, text in endnotes_entries:
            t = text
            # Remove bidi controls and hard spaces that may block matching
            t = "".join(ch for ch in t if ch not in BIDI_CTRL)
            t = t.replace("\u00A0", " ").replace("\u202F", " ")
            # Robustly strip ANY leading numeric token(s) + punctuation (Arabic/Latin), including nested parentheses/brackets
            patt = _re.compile(r"^\s*[\(\[\{\uFD3E]?\s*[0-9\u0660-\u0669\u06F0-\u06F9]+\s*[\)\]\}\uFD3F]?\s*[\.\-–—:\u060C\u066B\u066C\u06D4\u061B]*\s*")
            while True:
                t2 = patt.sub("", t)
                if t2 == t:
                    break
                t = t2
            t = t.lstrip()
            t_xml = xsu.escape(t)
            ch_id = gid_to_ch.get(gid, -1)
            ch_file = chid_to_fname.get(ch_id, "")
            back_href = f"{ch_file}#ref-{gid}" if ch_file else f"#ref-{gid}"
            # Optional section backlink
            sec_id = gid_to_sec.get(gid)
            sec_link = ""
            if sec_id and ch_file:
                key = f"{ch_id}:{sec_id}"
                sec_t = sec_title.get(key, "")
                if sec_t:
                    sec_link = f" <span class=\"note-sec\">— <a href=\"{xsu.escape(ch_file)}#{xsu.escape(sec_id)}\">{xsu.escape(sec_t)}</a></span>"
                else:
                    sec_link = f" <span class=\"note-sec\">— <a href=\"{xsu.escape(ch_file)}#{xsu.escape(sec_id)}\">§</a></span>"
            items_xml.append(
                f"<li id=\"note-{gid}\">{t_xml} <a href=\"{xsu.escape(back_href)}\">↩︎</a>{sec_link}</li>"
            )
        ol = "\n".join(items_xml)
        end_xhtml = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" xml:lang=\"%s\" lang=\"%s\" dir=\"rtl\">\n"
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
        ) % (meta.language, meta.language, xsu.escape("الهوامش"), xsu.escape("الهوامش"), ol)
        text_files.append((end_fname, end_xhtml.encode("utf-8")))
        toc_entries.append(
            {
                "title": "الهوامش",
                "href": end_fname,
                "children": [],
            }
        )

    font_manifest_xml = [
        f"    <item id=\"font_{xsu.escape(base)}\" href=\"fonts/{xsu.escape(base)}\" media-type=\"{xsu.escape(_mime)}\"/>"
        for base, _data, _mime in embed_fonts_payload
    ]

    cover_manifest_xml = []
    if cover_asset:
        cover_name, _cover_bytes, cover_mime = cover_asset
        cover_manifest_xml.append(
            f"    <item id=\"cover-image\" href=\"images/{xsu.escape(cover_name)}\" media-type=\"{xsu.escape(cover_mime)}\" properties=\"cover-image\"/>"
        )

    if minimal_profile:
        dc_publisher = ""
        creator_val = meta.author_page or meta.author or ""
        dc_creator = f"<dc:creator>{xsu.escape(creator_val)}</dc:creator>" if creator_val else ""
        dc_title = xsu.escape(meta.title)
    else:
        dc_publisher = f"    <dc:publisher>{xsu.escape(meta.publisher)}</dc:publisher>\n" if meta.publisher else ""
        dc_creator = f"<dc:creator>{xsu.escape(meta.author)}</dc:creator>" if meta.author else ""
        dc_title = xsu.escape(meta.book_title or meta.title)

    meta_cover_hint = "    <meta name=\"cover\" content=\"cover-image\"/>\n" if cover_asset else ""

    content_opf = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"2.0\" unique-identifier=\"book-id\">\n"
        "  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:opf=\"http://www.idpf.org/2007/opf\">\n"
        "    <dc:identifier id=\"book-id\">%s</dc:identifier>\n"
        "    <dc:title>%s</dc:title>\n"
        "    <dc:language>%s</dc:language>\n"
        f"{dc_publisher}"
        f"    {dc_creator}\n"
        f"{meta_cover_hint}"
        "  </metadata>\n"
        "  <manifest>\n"
        "    <item id=\"ncx\" href=\"toc.ncx\" media-type=\"application/x-dtbncx+xml\"/>\n"
        "    <item id=\"css\" href=\"css/style.css\" media-type=\"text/css\"/>\n"
        "%s\n"
        "%s\n"
        "%s\n"
        "  </manifest>\n"
        "  <spine toc=\"ncx\" page-progression-direction=\"rtl\">\n"
        "%s\n"
        "  </spine>\n"
        "</package>\n"
    ) % (
        xsu.escape(book_id),
        dc_title,
        xsu.escape(meta.language),
        "\n".join(font_manifest_xml),
        "\n".join(cover_manifest_xml),
        "\n".join(manifest_items),
        "\n".join(spine_items),
    )

    if not toc_entries and chapters_sorted:
        first_fname = f"text/{1:04d}.xhtml"
        toc_entries.append(
            {
                "title": chapters_sorted[0].title,
                "href": first_fname,
                "children": [],
            }
        )

    nav_counter = [1]

    def build_navpoint(entry: Dict[str, object], depth: int = 1) -> List[str]:
        idx = nav_counter[0]
        nav_counter[0] += 1
        indent = "  " * depth
        title = xsu.escape(str(entry.get("title", "")))
        href = xsu.escape(str(entry.get("href", "")))
        lines = [
            f"{indent}<navPoint id=\"navPoint-{idx}\" playOrder=\"{idx}\">",
            f"{indent}  <navLabel><text>{title}</text></navLabel>",
            f"{indent}  <content src=\"{href}\"/>",
        ]
        for child in entry.get("children", []) or []:
            if isinstance(child, dict):
                lines.extend(build_navpoint(child, depth + 1))
        lines.append(f"{indent}</navPoint>")
        return lines

    navmap_lines: List[str] = []
    for entry in toc_entries:
        navmap_lines.extend(build_navpoint(entry, 1))

    if not navmap_lines:
        navmap_lines.append(
            '    <navPoint id="navPoint-1" playOrder="1"><navLabel><text>المتن</text></navLabel><content src="text/0001.xhtml"/></navPoint>'
        )

    nav_depth = "2" if any((entry.get("children") for entry in toc_entries)) else "1"
    doc_title_text = xsu.escape(meta.book_title or meta.title or "كتاب")

    toc_ncx = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<ncx xmlns=\"http://www.daisy.org/z3986/2005/ncx/\" version=\"2005-1\">\n"
        "  <head>\n"
        "    <meta name=\"dtb:uid\" content=\"%s\"/>\n"
        "    <meta name=\"dtb:depth\" content=\"%s\"/>\n"
        "    <meta name=\"dtb:totalPageCount\" content=\"0\"/>\n"
        "    <meta name=\"dtb:maxPageNumber\" content=\"0\"/>\n"
        "  </head>\n"
        "  <docTitle><text>%s</text></docTitle>\n"
        "  <navMap>\n"
        "%s\n"
        "  </navMap>\n"
        "</ncx>\n"
    ) % (
        xsu.escape(book_id),
        nav_depth,
        doc_title_text,
        "\n".join(navmap_lines),
    )

    with zipfile.ZipFile(out_path, "w") as zf:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, mimetype)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/css/style.css", css)
        zf.writestr("OEBPS/toc.ncx", toc_ncx.encode("utf-8"))
        zf.writestr("OEBPS/content.opf", content_opf.encode("utf-8"))
        for fname, data in text_files:
            zf.writestr(f"OEBPS/{fname}", data)
        for base, data, _mime in embed_fonts_payload:
            zf.writestr(f"OEBPS/fonts/{base}", data)
        if cover_asset:
            cover_name, cover_bytes, _cover_mime = cover_asset
            zf.writestr(f"OEBPS/images/{cover_name}", cover_bytes)
        # Embed inline images from chapters, if any
        if inline_images:
            for base, data, _mime in inline_images:
                zf.writestr(f"OEBPS/images/{base}", data)
