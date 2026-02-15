build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f cianaparrot

restart:
	docker compose restart

shell:
	docker compose exec cianaparrot bash
