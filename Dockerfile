FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Системные зависимости (минимум), можно расширить при необходимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Кэширование зависимостей: сначала только метаданные проекта
COPY pyproject.toml /app/
COPY README.md README.en.md README.ar.md /app/

# Установим dev-инструменты и сам пакет (editable)
RUN pip install --upgrade pip \
 && pip install pytest ruff black

# Копируем исходники и тесты
COPY src /app/src
COPY tests /app/tests
COPY docs /app/docs
COPY AGENTS.md ROADMAP.md TECHNICAL.md /app/

# Установка пакета в editable режиме
RUN pip install -e .

# Команда по умолчанию — показать помощь CLI
CMD ["python", "-m", "shamela_books", "--help"]

