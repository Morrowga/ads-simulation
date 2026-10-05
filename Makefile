SHELL := /bin/bash
COMPOSE ?= docker compose
HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)

.PHONY: env up down logs restart ps shell dbshell migrate migration seed test lint format smoke openapi engine reset-db build

## Create .env from .env.example (only if missing) and write the current UID/GID into it
env:
	@if [ ! -f .env ]; then cp .env.example .env; echo "created .env from .env.example"; fi
	@if grep -q '^UID=' .env; then sed -i.bak 's/^UID=.*/UID=$(HOST_UID)/' .env; else echo "UID=$(HOST_UID)" >> .env; fi
	@if grep -q '^GID=' .env; then sed -i.bak 's/^GID=.*/GID=$(HOST_GID)/' .env; else echo "GID=$(HOST_GID)" >> .env; fi
	@rm -f .env.bak
	@echo "UID=$(HOST_UID) GID=$(HOST_GID) written to .env"

build: env
	$(COMPOSE) build

## Start the whole stack (postgres, redis, minio, mailpit, api, worker)
up: env
	$(COMPOSE) up -d --build
	@echo "API docs: http://localhost:8000/docs  Mailpit: http://localhost:8025  MinIO: http://localhost:9001"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker

restart:
	$(COMPOSE) restart api worker

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec api bash

dbshell:
	$(COMPOSE) exec postgres psql -U advar -d advar

migrate:
	$(COMPOSE) exec api alembic upgrade head

## Autogenerate a migration as the host user: make migration m="add foo"
migration:
	@test -n "$(m)" || (echo "usage: make migration m=\"message\"" && exit 1)
	$(COMPOSE) exec --user "$(HOST_UID):$(HOST_GID)" api alembic revision --autogenerate -m "$(m)"

seed:
	$(COMPOSE) exec api python -m scripts.seed

## Run the test suite inside the api container with mock LLM and mock payments
test:
	$(COMPOSE) exec -e APP_ENV=test -e LLM_PROVIDER=mock -e PAYMENT_MODE=mock -e QUEUE_BACKEND=inline -e STORAGE_BACKEND=memory -e MAIL_BACKEND=memory api pytest -q

lint:
	$(COMPOSE) exec api ruff check app engine scripts tests

format:
	$(COMPOSE) exec api ruff format app engine scripts tests
	$(COMPOSE) exec api ruff check --fix app engine scripts tests

## End-to-end smoke test against the running stack (mock LLM + mock payments)
smoke:
	$(COMPOSE) exec api python -m scripts.smoke_test

## Write backend/openapi.json for the frontend
openapi:
	$(COMPOSE) exec api python -m scripts.export_openapi
	@echo "wrote backend/openapi.json"

## Run the engine from the command line: make engine [AD=samples/sample_test.json]
AD ?= samples/sample_test.json
engine:
	$(COMPOSE) exec api python -m engine.cli run $(AD)

## Drop all data volumes (asks for confirmation)
reset-db:
	@read -p "This deletes postgres, minio and venv volumes. Continue? [y/N] " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then $(COMPOSE) down -v; echo "volumes removed"; else echo "aborted"; fi
