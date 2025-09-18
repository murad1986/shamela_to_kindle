# Разработка

## Структура проекта

- `src/shamela_books/` — библиотека (API, парсеры, сборщик EPUB, CLI):
  - `api.py` — высокоуровневый `build_epub_from_url(...)`.
  - `parsers.py` — TOC/метаданные/контент‑парсер.
  - `endnotes.py` — извлечение/линковка/генерация сносок.
  - `builder.py` — генерация XHTML/OPF/ZIP.
  - `cover.py` — получение/валидация/конвертация обложек.
  - `http.py` — `fetch`, `RateLimiter`.
  - `providers.py` — протокол поставщиков и `ShamelaProvider` по умолчанию.
  - `sanitizer.py` — профилируемый санитайзер (при наличии bleach).
  - `cache.py` — простой байтовый кэш (HTML/изображения/обложки).
  - `cli.py` — тонкий CLI над API.

## Бутстрап

- Окружение:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
- Стиль/линт:
  - `ruff check src tests`
  - `black src tests`
- Тесты:
  - `pytest -q`

## Публичный API

- `build_epub_from_url(url, *, profile='minimal', use_cache=True, on_event=None, provider=None, ...) -> str`
- `fetch_toc(url, *, provider=None) -> list[(id, title, url)]`
- `fetch_chapter(book_url, chapter_url, *, provider=None) -> str`
- Протокол `Provider`: `fetch_index(url, use_cache) -> str`, `fetch_chapter(url, referer, use_cache) -> str`
- Колбэк прогресса: `on_event(ev: dict)`; события `chapter_fetch_start`/`chapter_fetch_done` с `index` и `id`.
- Исключения: `ShamelaError`.

## Реализация

- Главы очищаются профилируемым санитайзером; внешние изображения встраиваются, `src` переписывается.
- Вложенное оглавление строится по `h2/h3` внутри глав; `id` стабильны (`sec-<chapterId>-<n>`).
- Сноски глобально нумеруются; на странице «الهوامش» добавляется ссылка на ближайший раздел.
- EPUB: `nav.xhtml` присутствует; landmarks добавлены; для Kindle nav не в `spine`.

## Коммиты и PR

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:` …
- Изменения по Apple Books/Kindle описывать отдельно (различные требования).

## Безопасность

- Не коммитим секреты. Данные — в `data/` (gitignore).
- Парсинг HTML — без выполнения JS; сетевой ввод — валидируем и ограничиваем rate‑лимитером.
