from pathlib import Path
from shamela_books import ContentParser


def test_content_clean_icons_and_buttons_removed_keep_sup_and_anchors():
    html = Path('tests/fixtures/chapter.html').read_text(encoding='utf-8')
    cp = ContentParser()
    cp.feed(html)
    body = cp.get_content()
    assert 'fa ' not in body and '<button' not in body and '<i ' not in body
    assert '<sup>' in body
    assert 'id="a1"' in body or 'id=\"a1\"' in body


def test_content_parser_keeps_multiple_nass_blocks():
    html = """
    <div class="nass"><p>الأول.</p></div>
    <div class="nass"><p>الثاني.</p></div>
    """
    cp = ContentParser()
    cp.feed(html)
    body = cp.get_content()
    assert 'الأول.' in body and 'الثاني.' in body
    assert body.index('الأول.') < body.index('الثاني.')
