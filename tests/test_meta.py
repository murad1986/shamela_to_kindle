from pathlib import Path
from scripts.shamela_to_epub import parse_book_meta, strip_book_prefix


def test_parse_book_meta_clean_title_author():
    html = Path('tests/fixtures/book_index.html').read_text(encoding='utf-8')
    meta = parse_book_meta(html)
    assert meta.book_title == 'الجواب الكافي لمن سأل عن الدواء الشافي أو الداء والدواء'
    assert 'ابن قيم' in (meta.author or '') or 'ابن القيم' in (meta.author or '')


def test_strip_book_prefix():
    s = strip_book_prefix('الكتاب: الجواب الكافي')
    assert s.startswith('الجواب')
