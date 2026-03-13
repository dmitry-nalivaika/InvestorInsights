# Appendix F: Makefile Commands

> Referenced from [System Specification](../system_specification.md)

```makefile
# Makefile — Common commands for development and operations

.PHONY: help setup up down logs test lint migrate seed backup

help:                               ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk \
		'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup & Infrastructure ──────────────────────────────────
setup:                              ## First-time setup (copy .env, build images)
	cp -n .env.example .env || true
	docker compose build
	docker compose run --rm api alembic upgrade head
	docker compose run --rm api python -m app.scripts.seed_defaults

up:                                 ## Start all services
	docker compose up -d

up-full:                            ## Start all services including monitoring
	docker compose --profile monitoring up -d

down:                               ## Stop all services
	docker compose down

restart:                            ## Restart all services
	docker compose restart

logs:                               ## Tail logs for all services
	docker compose logs -f --tail=100

logs-api:                           ## Tail API logs
	docker compose logs -f --tail=100 api

logs-worker:                        ## Tail worker logs
	docker compose logs -f --tail=100 worker

# ── Database ────────────────────────────────────────────────
migrate:                            ## Run database migrations
	docker compose run --rm api alembic upgrade head

migrate-new:                        ## Create new migration (pass MESSAGE="description")
	docker compose run --rm api alembic revision --autogenerate -m "$(MESSAGE)"

migrate-rollback:                   ## Rollback last migration
	docker compose run --rm api alembic downgrade -1

db-shell:                           ## Open PostgreSQL shell
	docker compose exec postgres psql -U analyst -d company_analysis

# ── Testing ─────────────────────────────────────────────────
test:                               ## Run all tests (unit + integration)
	docker compose run --rm api pytest tests/unit tests/integration -v

test-unit:                          ## Run unit tests only
	docker compose run --rm api pytest tests/unit -v

test-integration:                   ## Run integration tests only
	docker compose run --rm api pytest tests/integration -v

test-e2e:                           ## Run end-to-end tests
	docker compose run --rm api pytest tests/e2e -v --timeout=300

test-coverage:                      ## Run tests with coverage report
	docker compose run --rm api pytest tests/unit tests/integration \
		--cov=app --cov-report=html --cov-report=term --cov-fail-under=85

test-frontend:                      ## Run frontend tests
	docker compose run --rm frontend npm test

# ── Code Quality ────────────────────────────────────────────
lint:                               ## Run linters
	docker compose run --rm api ruff check app/
	docker compose run --rm api ruff format --check app/
	docker compose run --rm api mypy app/ --strict

lint-fix:                           ## Auto-fix linting issues
	docker compose run --rm api ruff check --fix app/
	docker compose run --rm api ruff format app/

# ── Data & Operations ──────────────────────────────────────
seed:                               ## Seed default analysis profile
	docker compose run --rm api python -m app.scripts.seed_defaults

backup:                             ## Run backup of all data stores
	./scripts/backup.sh

reset:                              ## ⚠️  Wipe ALL data (development only)
	docker compose down -v
	docker compose up -d
	sleep 5
	$(MAKE) migrate
	$(MAKE) seed

# ── Debugging ──────────────────────────────────────────────
shell:                              ## Open Python shell in API container
	docker compose run --rm api python

flower:                             ## Open Celery Flower (task monitor)
	@echo "Flower UI: http://localhost:5555"
	docker compose --profile monitoring up -d worker-monitor

qdrant-dashboard:                   ## Show Qdrant dashboard URL
	@echo "Qdrant Dashboard: http://localhost:6333/dashboard"

minio-console:                      ## Show MinIO console URL
	@echo "MinIO Console: http://localhost:9001"
```
