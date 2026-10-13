.PHONY: up down logs restart test lint backup restore reset demo

up:
	@test -f .env || cp .env.example .env
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100 api

restart:
	docker compose restart

test:
	docker compose run --rm --no-deps api pytest -q

lint:
	ruff check .

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh $(FILE)

# ATTENTION : supprime les données (volumes)
reset:
	docker compose down -v
	docker compose up -d --build

demo: reset
