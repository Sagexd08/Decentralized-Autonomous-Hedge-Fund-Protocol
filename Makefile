# IRIS Protocol
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down logs ps build verify db-migrate db-seed db-shell test anchor-test verify-all clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Boot the full stack (web, api, db, redis)
	$(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory verify

down: ## Stop the stack, keep the database volume
	$(COMPOSE) down

build: ## Rebuild images without starting
	$(COMPOSE) build

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Tail logs from every service
	$(COMPOSE) logs -f

verify: ## Phase 1 gate: all three services answer 200
	@python scripts/verify_phase1.py

db-migrate: ## Apply migrations to a running database
	$(COMPOSE) exec -T db psql -U iris -d iris < db/migrations/0001_init.sql

db-seed: ## Load development seed data
	$(COMPOSE) exec -T db psql -U iris -d iris < db/seed/0001_seed.sql

db-shell: ## Open a psql shell
	$(COMPOSE) exec db psql -U iris -d iris

verify-all: ## Run every phase gate in order
	python scripts/verify_phase1.py
	python scripts/verify_phase2.py
	python scripts/verify_phase3.py
	python scripts/verify_phase4.py

anchor-test: ## Phase 2 gate: Anchor program tests (Linux container)
	docker build -f docker/anchor.Dockerfile -t iris-anchor-test .
	docker run --rm 	  -v "$(CURDIR)/programs/iris":/work 	  -v iris-cargo-registry:/usr/local/cargo/registry 	  -v iris-cargo-target:/work/target 	  iris-anchor-test

test: ## Run the API test suite
	$(COMPOSE) exec api pytest tests/ -v --tb=short

clean: ## Stop the stack and DROP the database volume
	$(COMPOSE) down -v
