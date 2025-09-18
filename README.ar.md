shamela_books — تحويل كتب الشاملة إلى EPUB (اتجاه RTL)

أداة خفيفة لبناء ملفات EPUB متوافقة مع Kindle وApple Books من موقع `shamela.ws`، مع الحفاظ على النص العربي واتجاه القراءة من اليمين إلى اليسار، فهرس متداخل (h2/h3)، صور مضمّنة، وسُطور سفلية (الهوامش) عالمية.

## خلاصة سريعة (TL;DR)
- الأساس: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- الغلاف: `--cover-auto` أو `--cover path/to.jpg|png`
- الملفات الشخصية: `--profile minimal|kindle|apple`
- بدون كاش: `--no-cache`
- الناتج الافتراضي: `output/<العنوان> - <الناشر>.epub`

## بنية المستودع
- `src/shamela_books/`: مكتبة (محللات، مُنشئ EPUB، مزودون، كاش، CLI).
- `output/`: المخرجات (غير متتبَّعة في git).

## الملفات الشخصية (Profiles)
- Minimal (افتراضي): XHTML نظيف RTL، مع معالم (landmarks)، فهرس متداخل من h2/h3، صور مضمّنة، و`endnotes.xhtml`.
- Kindle: مثل Minimal مع تنظيف محافظ مناسب لـ Send‑to‑Kindle.
- Apple: تنظيف أشدّ (مجموعة وسوم آمنة) و`xmlns:epub` عند استخدام `epub:type`.

## طريقة الاستخدام
- كتاب كامل: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- مع غلاف: `--cover-auto` أو `--cover path/to.jpg|png`
- تجربة سريعة (أول N فصل): `--limit N`
- الملف الناتج: `<العنوان> - <الناشر>.epub` (نحذف بادئة «كتاب/الكتاب»، ونحافظ على العربية).

## الخيارات
- `-o, --output`: مسار الملف الناتج.
- `--throttle <ثوانٍ>`: مهلة بين الطلبات (الافتراضي 0.8).
- `--limit <N>`: جلب أول N فصل (للاختبار).
- `--profile minimal|kindle|apple`: ملف شخصي للتعقيم والدلالة (sanitizer/semantics).
- `--no-cache`: تعطيل الكاش المحلي لصفحات HTML والصور.
- الغلاف:
  - `--cover-auto`: بحث تلقائي (Google/DuckDuckGo/Bing) مع مرشحات الحجم/النوع/النسبة البعدية.
  - `--cover <file>`: غلاف محلي (JPEG/PNG).
  - `--cover-min-size WxH`، `--cover-min-bytes B`، `--cover-convert-jpeg`.
- التوازي: `--workers 1..4` و`--jitter 0..1`.

### ملخص الخيارات

| الخيار | الوصف | الافتراضي | المثال |
|---|---|---|---|
| `-o, --output <path>` | مسار ملف الإخراج | `output/<العنوان> - <الناشر>.epub` | `-o output/book.epub` |
| `--throttle <sec>` | مهلة بين طلبات HTTP | `0.8` | `--throttle 0.6` |
| `--limit <N>` | جلب أول N فصل | كل الفصول | `--limit 10` |
| `--profile <p>` | ملف شخصي للتعقيم | `minimal` | `--profile apple` |
| `--no-cache` | تعطيل الكاش | معطّل | `--no-cache` |
| `--cover-auto` | بحث تلقائي عن غلاف | معطّل | `--cover-auto` |
| `--cover <file>` | غلاف محلي (JPEG/PNG) | لا يوجد | `--cover cover.jpg` |
| `--workers <n>` | عدد الخيوط | `2` | `--workers 2` |
| `--jitter <f>` | تذبذب المهلة 0..1 | `0.3` | `--jitter 0.1` |

## الغلاف
- بحث متسلسل: Google → DuckDuckGo → Bing (بدون JS). مع مرشحات النوع (JPEG/PNG)، الحجم، والنسبة البعدية.
- ملف محلي: JPEG/PNG (مستحسن ≥ 600×800). خيار `--cover-convert-jpeg` يحوّل PNG إلى JPEG.

## الفهرس المتداخل والصور
- عناوين `h2/h3` داخل الفصول تحصل على معرفات ثابتة وتظهر كبنود متداخلة في `nav.xhtml`.
- الصور الخارجية `<img src=...>` تُنزَّل وتُضمَّن في `OEBPS/images/` مع إعادة كتابة `src`.

## الهوامش (الهوامش)
- التعرف: `(N)`، `[N]`، `<sup>…</sup>`، والأرقام العربية. يدعم عدة كتل `p.hamesh` في نهاية الفصل مع إزالة التكرارات.
- الترقيم: عالمي على مستوى الكتاب؛ الروابط من النص → `endnotes.xhtml#note-<G>`؛ السهم ↩︎ يعود إلى `#ref-<G>`.
- مرجع القسم: تعرض صفحة «الهوامش» رابطًا إلى أقرب قسم `h2/h3` داخل الفصل.

## كمكتبة
```python
from shamela_books import build_epub_from_url, fetch_toc, Provider, ShamelaProvider

def on_event(ev: dict):
    if ev.get('type') == 'chapter_fetch_start':
        print('start', ev.get('index'), ev.get('id'))

out = build_epub_from_url(
    'https://shamela.ws/book/158',
    throttle=0.8,
    profile='apple',
    cover_auto=True,
    on_event=on_event,
)
print('EPUB at', out)
```

## ما يعمل
- ملفات minimal/kindle/apple، فهرس متداخل (h2/h3)، صور مضمّنة (JPEG/PNG)، وهوامش عالمية مع روابط رجوع.

تفاصيل تقنية أكثر: انظر `TECHNICAL.md`.
