.PHONY: up down build logs ps backup restore dev-backend dev-frontend

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up -d --build

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

backup:
	@mkdir -p /opt/buhgalteria-backups
	@TS=$$(date +%Y%m%d_%H%M%S); \
	docker compose exec -T db pg_dump -U buh buhdb | gzip > /opt/buhgalteria-backups/buhdb_$$TS.sql.gz; \
	echo "Backup: /opt/buhgalteria-backups/buhdb_$$TS.sql.gz"

bot-up:
	docker compose --profile bot up -d --build bot

bot-down:
	docker compose --profile bot stop bot

# Локальная разработка (без Docker)
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
