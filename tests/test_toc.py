from pathlib import Path
from shamela_books import parse_toc


def test_parse_toc_order_and_unique():
    html = Path('tests/fixtures/book_index.html').read_text(encoding='utf-8')
    toc = parse_toc('https://shamela.ws/book/158', html)
    assert [t.title for t in toc[:3]] == [
        'لكل داء دواء',
        'القرآن شفاء',
        'الدعاء يدفع المكروه',
    ]
    ids = [t.id for t in toc]
    assert len(ids) == len(set(ids))
