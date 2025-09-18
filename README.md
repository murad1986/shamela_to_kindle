shamela_books — парсер книг и сборщик EPUB (RTL)

[English](README.en.md) | [العربية](README.ar.md) | Русский

Проект для выгрузки книг с сайта `shamela.ws` и сборки EPUB с поддержкой RTL, вложенного оглавления (h2/h3), встроенных картинок и глобальных сносок, совместимых с Kindle и Apple Books.

## TL;DR
 - Базово: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
 - С обложкой: `--cover-auto` или `--cover path/to.jpg|png`
 - Профили: `--profile minimal|kindle|apple`
 - Без кэша: `--no-cache`
 - Результат: `output/<Название книги> - <Издатель>.epub`

## Установка (опционально)
- Локально: `pip install -e .`
- Через pipx: `pipx install .`
- Запуск CLI: `shamela-to-epub 'https://shamela.ws/book/158' --throttle 0.6`

## Структура
- `src/shamela_books/` — библиотека (парсеры, сборщик EPUB, CLI).
- `output/` — готовые файлы (EPUB).
- `docs/` — подробная документация (использование, сноски, Apple Books, разработка).

## Быстрый старт
- Python 3.11+: `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
- Через CLI: `shamela-to-epub 'https://shamela.ws/book/158' --throttle 0.6`
- Профиль для Apple: `--profile apple`; для Kindle: `--profile kindle`
- С обложкой: `--cover-auto` или `--cover path/to.jpg|png`
- Результат: `output/<Название книги> - <Издатель>.epub`.

## Документация
- Руководство по использованию (RU/EN): `docs/USAGE.ru.md`, `docs/USAGE.en.md`
- Сноски: дизайн и реализация (RU/EN): `docs/ENDNOTES.ru.md`, `docs/ENDNOTES.en.md`
- Совместимость с Apple Books (RU/EN): `docs/APPLE_BOOKS.ru.md`, `docs/APPLE_BOOKS.en.md`
- Разработка/контрибуции (RU/EN): `docs/DEVELOPMENT.ru.md`, `docs/DEVELOPMENT.en.md`
- Диагностика и FAQ (RU/EN): `docs/TROUBLESHOOTING.ru.md`, `docs/TROUBLESHOOTING.en.md`
- Технические детали: `TECHNICAL.md`

## Использование как модуль
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
    cover_min_size=(600, 800),
    on_event=on_event,
)
print('EPUB at', out)
```

## Профили и формат
- Minimal (по умолчанию): чистый RTL XHTML, landmarks, вложенное оглавление (h2/h3), встроенные картинки, страница «الهوامش».
- Kindle: как minimal, но санитайзер настроен под приемистость Send‑to‑Kindle.
- Apple: более строгий санитайзер, явный `xmlns:epub` при использовании `epub:type`.

## Ключевые опции
- `-o, --output` — путь к выходному файлу.
- `--throttle <сек>` — пауза между запросами.
- `--limit <N>` — ограничить число глав.
- `--profile minimal|kindle|apple` — профиль санитайзера/семантики.
- `--no-cache` — отключить локальный кэш (HTML/картинки/обложки).
- Обложка:
  - `--cover-auto` — автопоиск (Google/DuckDuckGo/Bing) с фильтрами размера/типа/аспекта.
  - `--cover <file>` — локальный файл (JPEG/PNG), `--cover-min-size`, `--cover-min-bytes`, `--cover-convert-jpeg`.
- Параллелизм: `--workers 1..4`, `--jitter 0..1`.

### Сводная таблица опций

| Опция | Описание | По умолчанию | Пример |
|---|---|---|---|
| `-o, --output <path>` | Путь к выходному файлу | `output/<Название> - <Издатель>.epub` | `-o output/book.epub` |
| `--throttle <sec>` | Пауза между HTTP‑запросами | `0.8` | `--throttle 0.6` |
| `--limit <N>` | Скачивать только первые N глав (для теста) | все главы | `--limit 10` |
| `--profile <p>` | Профиль санитайзера | `minimal` | `--profile apple` |
| `--no-cache` | Отключить кэш | выкл | `--no-cache` |
| `--cover-auto` | Автопоиск обложки (Google/DuckDuckGo/Bing) | выкл | `--cover-auto` |
| `--cover <file>` | Локальная обложка (JPEG/PNG, ≥ 300×300) | отсутствует | `--cover cover.jpg` |
| `--workers <n>` | Потоки | `2` | `--workers 2` |
| `--jitter <f>` | Джиттер задержки 0..1 | `0.3` | `--jitter 0.1` |

## Обложка
- Поиск: Google → DuckDuckGo → Bing (без JS). Фильтры по типу (JPEG/PNG), размеру и аспект‑ratio. Можно задать `--cover-query`.
- Локальный файл: JPEG/PNG (рекомендуется ≥ 600×800 для обложки). `--cover-convert-jpeg` конвертирует PNG в JPEG.

## Сноски (الهوامش)
- Распознавание: `(N)`, `[N]`, `<sup>…</sup>`, арабские цифры. Поддержка нескольких блоков `p.hamesh` в конце главы; дедуп по номеру.
- Нумерация: глобальная по книге; ссылки из текста → `endnotes.xhtml#note-<G>`; ↩︎ ведёт назад на `#ref-<G>`.
- Привязка к разделам: на странице «الهوامش» показывается ссылка на ближайший раздел `h2/h3` («— Название раздела»).

## Что работает
- Минимальный/Kindle/Apple профили, вложенное оглавление (h2/h3), встроенные изображения (JPEG/PNG), глобальные сноски с обратными ссылками.

Подробнее о профилях, навигации и обложках: см. TECHNICAL.md.

## Кэш
- По умолчанию включён файловый кэш HTML и картинок в `.cache/shamela_books/`.
- Можно переопределить каталог через переменную `SHAMELA_CACHE_DIR`.
- Отключение: `--no-cache` в CLI или `use_cache=False` в API.

## Пример
- `python -m shamela_books 'https://shamela.ws/book/158' --throttle 0.6`
