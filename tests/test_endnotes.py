from pathlib import Path
from scripts.shamela_to_epub import extract_endnotes, link_endnote_refs, build_endnotes_xhtml


def test_extract_endnotes_from_hamesh():
    html = Path('tests/fixtures/chapter_endnotes.html').read_text(encoding='utf-8')
    body, notes = extract_endnotes(html)
    # hamesh and hr removed
    assert 'hamesh' not in body and '<hr' not in body
    # three notes
    assert notes == [('1', 'الأولى.'), ('2', 'الثانية.'), ('3', 'الثالثة.')]


def test_link_endnote_refs():
    html = "<p>نص (١) و(٢).</p>"
    linked = link_endnote_refs(html, {'1': 1, '2': 2})
    assert 'href="#note-1"' in linked and 'id="ref-1"' in linked
    assert 'href="#note-2"' in linked and 'id="ref-2"' in linked


def test_build_endnotes_xhtml():
    xhtml = build_endnotes_xhtml('ar', [(1, 'الأولى.'), (2, 'الثانية.')])
    assert '<ol' in xhtml and 'note-1' in xhtml and 'note-2' in xhtml
    assert '↩︎' in xhtml
