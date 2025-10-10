# Repository Guidelines

## Codex Handoff Snapshot
- **Purpose**: `shamela_books` converts Shamela.ws books into RTL EPUBs optimized for Kindle/Apple readers via a library-first architecture exposing `build_epub_from_url`.
- **Key Entry Points**: Public API lives in `src/shamela_books/__init__.py`; CLI runs through `python -m shamela_books` delegating to `cli.main`.
- **Core Modules**:
  - `api.py` orchestrates fetching, parsing, sanitizing, cover selection, and EPUB assembly.
  - `builder.py` creates chapter XHTML, packages EPUB3, and normalizes filenames.
  - `parsers.py` extracts metadata, TOC, and cleans chapter HTML; `endnotes.py` handles حاشية footnotes.
  - `http.py` + `cache.py` provide polite downloading with caching; `cover.py` manages cover sourcing.
- **Data & Fixtures**: Sample HTML lives under `tests/fixtures/` for deterministic parsing/endnote tests; generated EPUBs land in `output/` (gitignored).
- **Setup**: `python3.11 -m venv .venv && source .venv/bin/activate`, then `pip install -e .[dev]` (or run `scripts/dev_setup.sh` which performs the same bootstrap inside the repo).
- **Validation**: Run `pytest -q`; linters available via `ruff check src tests` and `black src tests`. Optional type check `mypy src`.
- **Operational Notes**: Default build throttles HTTP via `RateLimiter`; `build_epub_from_url` accepts callbacks for progress and supports caching toggles (`use_cache=False`) and profile-specific sanitizing (`minimal|kindle|apple`).
- **Коммуникация**: Всегда отвечать пользователю на русском языке, независимо от языка запроса.

## Project Structure & Module Organization
- Prefer a library-first layout with small CLIs.
- Suggested structure:
  - `src/shamela_books/`: source modules (public API under `__init__.py`).
  - `scripts/`: runnable utilities and ETL/CLI entry points.
  - `tests/`: unit/integration tests mirroring `src/` structure.
  - `assets/` and `data/`: static files and local datasets (gitignored if large).
  - `docs/`: ADRs, design notes, and usage guides.

## Build, Test, and Development Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`.
- Install deps: `pip install -e .` (with `pyproject.toml`/`setup.cfg`) or `pip install -r requirements.txt`.
- Run app/CLI: `python -m shamela_books` or scripts in `scripts/` (e.g., `python scripts/import_books.py`).
- Tests: `pytest -q`.
- Lint/format: `ruff check src tests` and `black src tests`.
- Type-check: `mypy src` (optional but recommended).

## Coding Style & Naming Conventions
- Python 3.11+, PEP 8, 4-space indentation.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for constants.
- Keep modules small and cohesive; prefer pure functions; document public APIs with docstrings.
- Tooling: configure `ruff`, `black`, `pytest`, and (optionally) `mypy` in `pyproject.toml`.

## Testing Guidelines
- Framework: `pytest` with `tests/test_*.py` and `tests/*/test_*.py`.
- Place shared fixtures in `tests/conftest.py`.
- Aim for ≥90% coverage on core logic; use `pytest -q --cov=src --cov-report=term-missing`.
- Write deterministic tests; avoid network and filesystem side effects (use temp dirs/mocks).

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits (e.g., `feat: add search index`, `fix(parser): handle Latin digits`).
- PRs: include purpose, linked issues, test plan, and before/after notes; add screenshots for user-facing changes.
- Keep PRs focused and under ~300 lines where possible; include tests and updated docs.

## Security & Configuration Tips
- Never commit secrets. Provide `./.env.example`; load via `dotenv` in local dev only.
- Large artifacts and raw datasets belong in `data/` and are gitignored; document reproducible steps to regenerate.
- Validate and sanitize external inputs; avoid executing untrusted content.
