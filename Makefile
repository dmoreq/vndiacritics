.PHONY: help install-dev format lint test check pre-commit-install pre-commit-run

help:
	@echo "Available commands:"
	@echo "  make install-dev       - Install package in editable development mode"
	@echo "  make format            - Format code using Ruff"
	@echo "  make lint              - Run linting checks using Ruff"
	@echo "  make test              - Run all tests"
	@echo "  make check             - Format, lint, and run tests"
	@echo "  make pre-commit-install - Install git pre-commit hooks"
	@echo "  make pre-commit-run    - Run all pre-commit hooks on all files"

install-dev:
	pip install -e ".[dev]"
	./scripts/fetch_corpus.sh

format:
	ruff format vndiacritics tests bench

lint:
	ruff check vndiacritics tests bench

test:
	pytest tests -q

check: format lint test

pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
