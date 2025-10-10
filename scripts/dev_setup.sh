#!/usr/bin/env bash
set -euo pipefail

# Быстрый сетап dev-окружения для проекта
# Требования: установлен python3.11 или выше и pip

PY=${PYTHON_BIN:-python3.11}

echo "[dev-setup] Использую интерпретатор: $PY"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Ошибка: не найден $PY. Установите Python 3.11+ или задайте PYTHON_BIN."
  exit 1
fi

"$PY" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip

if [ -f requirements.txt ]; then
  echo "[dev-setup] Устанавливаю зависимости из requirements.txt"
  pip install -r requirements.txt
fi

echo "[dev-setup] Устанавливаю пакет в editable-режиме"
pip install -e .

echo "[dev-setup] Устанавливаю инструменты разработки (pytest, ruff, black, coverage)"
pip install pytest ruff black coverage

echo "[dev-setup] Готово. Активируйте окружение: source .venv/bin/activate"

