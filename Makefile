# IRIS Protocol
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down logs ps build verify db-migrate db-seed db-shell test anchor-test verify-all warm settle feed score allocate risk events cycle devnet-build devnet-deploy devnet-address clean

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
	$(COMPOSE) exec -T db psql -U iris -d iris -v ON_ERROR_STOP=1 < db/migrations/0001_init.sql
	$(COMPOSE) exec -T db psql -U iris -d iris -v ON_ERROR_STOP=1 < db/migrations/0002_settlement.sql
	$(COMPOSE) exec -T db psql -U iris -d iris -v ON_ERROR_STOP=1 < db/migrations/0003_risk.sql
	$(COMPOSE) exec -T db psql -U iris -d iris -v ON_ERROR_STOP=1 < db/migrations/0004_events.sql

db-seed: ## Load development seed data
	$(COMPOSE) exec -T db psql -U iris -d iris < db/seed/0001_seed.sql

db-shell: ## Open a psql shell
	$(COMPOSE) exec db psql -U iris -d iris

verify-all: ## Run every phase gate in order
	python scripts/verify_phase1.py
	python scripts/verify_phase2.py
	python scripts/verify_phase3.py
	python scripts/verify_phase4.py
	python scripts/verify_phase5.py
	python scripts/verify_phase6.py
	python scripts/verify_phase7.py
	python scripts/verify_phase8.py
	python scripts/verify_phase9.py
	python scripts/verify_phase10_12.py

devnet-build: ## Build the Solana devnet toolchain image (solana 4.2.2 + SBF)
	docker build -f docker/devnet.Dockerfile -t iris-devnet .

devnet-deploy: devnet-build ## Build and deploy both programs to devnet
	docker volume create iris-devnet-keys >/dev/null
	MSYS_NO_PATHCONV=1 docker run --rm 	  -v "$(CURDIR)/programs/iris":/work 	  -v iris-devnet-keys:/keys 	  -v iris-cargo-registry:/usr/local/cargo/registry 	  iris-devnet

devnet-address: ## Print the devnet deployer address (fund this to deploy)
	MSYS_NO_PATHCONV=1 docker run --rm -v iris-devnet-keys:/keys 	  --entrypoint sh iris-devnet -c 	  'solana config set --url https://api.devnet.solana.com >/dev/null; 	   solana config set --keypair /keys/deployer.json >/dev/null; 	   echo "deployer $$(solana address)  balance $$(solana balance)"'

events: ## Tail the protocol event stream (ctrl-c to stop)
	$(COMPOSE) exec -T api python -m services.event_stream

risk: ## Run one risk sweep: breach -> freeze -> slash
	$(COMPOSE) exec -T api python -m agents.risk.engine

anchor-test: ## Phase 2 gate: Anchor program tests (Linux container)
	docker build -f docker/anchor.Dockerfile -t iris-anchor-test .
	docker run --rm 	  -v "$(CURDIR)/programs/iris":/work 	  -v iris-cargo-registry:/usr/local/cargo/registry 	  -v iris-cargo-target:/work/target 	  iris-anchor-test

test: ## Run both test suites — §4 root tree and the legacy api tree
	$(COMPOSE) exec -T api python -m pytest /repo/tests -q
	$(COMPOSE) exec -T api python -m pytest tests/ -q

warm: ## Fit and cache the model artifacts (~40s cold, ~0.2s after)
	$(COMPOSE) exec -T api python -c "from ml.inference.artifacts import warm; print(warm())"

settle: ## Run the Phase 5 settlement sweep against the live database
	$(COMPOSE) exec -T api python -m agents.evaluation.settlement

feed: ## Write a labelled simulated price tape (gap-filling, idempotent)
	$(COMPOSE) exec -T api python -m agents.evaluation.prices --asset BTC --hours 6

score: ## Compute and store the IRIS Score for every agent
	$(COMPOSE) exec -T api python -m agents.reputation.score

allocate: ## Run one MWU allocation step
	$(COMPOSE) exec -T api python -m agents.allocation.allocator

cycle: ## The full loop: feed -> settle -> score -> risk -> allocate
	@$(MAKE) --no-print-directory feed
	@$(MAKE) --no-print-directory settle
	@$(MAKE) --no-print-directory score
	@$(MAKE) --no-print-directory risk
	@$(MAKE) --no-print-directory allocate

clean: ## Stop the stack and DROP the database volume
	$(COMPOSE) down -v
