.PHONY: dev-backend dev-frontend test up down

dev-backend:
	cd backend && ../b2toc1venv/bin/uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && ../b2toc1venv/bin/pytest

up:
	docker compose up --build

down:
	docker compose down

