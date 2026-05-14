PYTHON ?= python3
BACKEND_DIR := apps/backend
FRONTEND_DIR := apps/frontend

.PHONY: install install-backend install-frontend dev lint test typecheck format docker-up docker-down seed

install: install-backend install-frontend

install-backend:
	$(PYTHON) -m pip install -e ".[dev]"

install-frontend:
	cd $(FRONTEND_DIR) && npm install

dev:
	docker compose -f docker-compose.dev.yml up --build

lint:
	ruff check .

format:
	ruff check . --fix

typecheck:
	mypy apps/backend

test:
	pytest

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

seed:
	$(PYTHON) scripts/seed_demo_data.py

