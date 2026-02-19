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

bridge-cc:
	@command -v claude >/dev/null 2>&1 || { echo "Error: claude CLI not found in PATH"; exit 1; }
	@claude auth status >/dev/null 2>&1 || { echo "Error: claude not authenticated. Run 'claude login'."; exit 1; }
	@echo "Starting Claude Code bridge on port 9842..."
	@exec python3 src/bridges/claude_code/server.py
