# Руководство по использованию

Этот документ описывает установку, запуск CLI, ключевые опции и советы по сборке EPUB‑книг из shamela.ws с поддержкой Kindle и Apple Books.

## Установка

- Виртуальное окружение (рекомендовано):
  - `python -m venv .venv && source .venv/bin/activate`
- Установка пакета для разработки:
  - `pip install -e .[dev]`

## Запуск CLI

- Через модуль:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8`
- Через консольную команду:
  - `shamela-to-epub 'https://shamela.ws/book/<id>' [опции]`

Выходной файл по умолчанию будет создан в каталоге `output/`.

## Опции

- `-o, --output <PATH>` — путь к файлу EPUB.
- `--throttle <сек>` — задержка между запросами (вежливый парсинг). Рекомендуется `0.6–1.0`.
- `--limit <N>` — ограничить число глав (для отладки).
- Обложка:
  - `--cover-auto` — автопоиск обложки (Google/DuckDuckGo/Bing, HTML‑парсинг без JS) с фильтрами.
  - `--cover <file>` — локальная обложка (JPEG/PNG/HEIC — при наличии Pillow/pillow‑heif);
  - `--cover-min-size WxH` — минимальный размер.
  - `--cover-min-bytes <B>` — минимальный размер файла.
  - `--cover-convert-jpeg` — конвертировать PNG/HEIC в JPEG (для Kindle).
- Параллелизм:
  - `--workers <1..4>` — число потоков.
  - `--jitter <0..1>` — джиттер задержки (в долях) для «более вежливой» нагрузки.

## Kindle vs Apple Books

- Kindle (Send‑to‑Kindle):
  - Минимальный EPUB‑профиль, без встроенных шрифтов, без «страницы обложки».
  - nav.xhtml присутствует в манифесте, но не добавляется в spine.
  - Сноски: глобальная нумерация по книге, `endnotes.xhtml` с обратными ссылками.
  - Обложка: JPEG (по возможности), слишком агрессивные шрифты/обложки могут приводить к e999.

- Apple Books:
  - Строгая XML‑валидация. Везде, где используется `epub:type`, объявляем `xmlns:epub`.
  - Контент глав проходит очистку: удаляются исходные `<span>/<a>`‑обёртки, балансируются теги.
  - Любые несоответствия XML («mismatch») устраняются принудительным закрытием и allowlist‑санитайзером.

## Примеры

- Базовый:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8`
- С автопоиском обложки:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --throttle 0.8 --cover-auto`
- С локальной обложкой и конвертацией в JPEG:
  - `python -m shamela_books 'https://shamela.ws/book/18128' --cover ./cover.heic --cover-convert-jpeg`

