from pathlib import Path
from scripts.shamela_to_epub import ContentParser


def test_content_clean_icons_and_buttons_removed_keep_sup_and_anchors():
    html = Path('tests/fixtures/chapter.html').read_text(encoding='utf-8')
    cp = ContentParser()
    cp.feed(html)
    body = cp.get_content()
    assert 'fa ' not in body and '<button' not in body and '<i ' not in body
    assert '<sup>' in body
    assert 'id="a1"' in body or 'id=\"a1\"' in body
