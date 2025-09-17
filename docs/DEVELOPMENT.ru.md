# Разработка

## Структура проекта

- `src/shamela_books/` — библиотека (API, парсеры, сборщик EPUB, CLI):
  - `api.py` — высокоуровневый `build_epub_from_url(...)`.
  - `parsers.py` — TOC/метаданные/контент‑парсер + санитайзер.
  - `endnotes.py` — извлечение/линковка/генерация сносок.
  - `builder.py` — генерация XHTML/OPF/ZIP.
  - `cover.py` — получение/валидация/конвертация обложек.
  - `http.py` — `fetch`, `RateLimiter`.
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

## Коммиты и PR

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:` …
- Изменения по Apple Books/Kindle описывать отдельно (различные требования).

## Безопасность

- Не коммитим секреты. Данные — в `data/` (gitignore).
- Парсинг HTML — без выполнения JS; сетевой ввод — валидируем и ограничиваем rate‑лимитером.

