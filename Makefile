PY?=python3.11

.PHONY: venv install test lint fmt check all

venv:
	$(PY) -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip

install: venv
	. .venv/bin/activate && pip install -e .
	. .venv/bin/activate && pip install pytest ruff black coverage

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check src tests

fmt:
	. .venv/bin/activate && black src tests

check:
	. .venv/bin/activate && ruff check src tests
	. .venv/bin/activate && black --check src tests
	. .venv/bin/activate && pytest -q

all: install check

.PHONY: docker-build docker-test docker-lint docker-cli

docker-build:
	docker build -t shamela-books:dev .

docker-test:
	docker run --rm -v "$(PWD)":/app shamela-books:dev pytest -q

docker-lint:
	docker run --rm -v "$(PWD)":/app shamela-books:dev ruff check src tests && \
	  docker run --rm -v "$(PWD)":/app shamela-books:dev black --check src tests

docker-cli:
	docker run --rm -it -v "$(PWD)":/app shamela-books:dev python -m shamela_books --help
