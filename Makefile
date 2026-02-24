.PHONY: build up down logs restart shell test gateway docs docs-build

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f cianaparrot

restart:
	docker compose build
	docker compose up -d

shell:
	docker compose exec cianaparrot bash

test:
	python3 -m pytest tests/ -v

gateway:
	@echo "Starting host gateway on port 9842..."
	@if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
	@.venv/bin/pip install -q --upgrade -r src/gateway/requirements.txt
	@exec .venv/bin/python src/gateway/server.py

docs:
	@if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
	@.venv/bin/pip install -q --upgrade -r requirements-docs.txt
	@.venv/bin/mkdocs serve

docs-build:
	@if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
	@.venv/bin/pip install -q --upgrade -r requirements-docs.txt
	@.venv/bin/mkdocs build
