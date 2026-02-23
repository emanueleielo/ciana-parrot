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
	@exec python3 src/gateway/server.py
