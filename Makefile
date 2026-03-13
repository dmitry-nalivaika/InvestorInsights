# ============================================================
# InvestorInsights — Makefile
# Common commands for development and operations.
#
# Ref: Appendix F (spec), tasks.md T015
#
# Local dev runs Python natively (.venv) with infra services
# in Docker (docker-compose.dev.yml).
# ============================================================

.DEFAULT_GOAL := help
SHELL := /bin/zsh

# ── Configurable variables ──────────────────────────────────
COMPOSE      := docker compose -f docker-compose.dev.yml
PYTHON       := .venv/bin/python
PIP          := .venv/bin/pip
PYTEST       := $(PYTHON) -m pytest
RUFF         := $(PYTHON) -m ruff
MYPY         := $(PYTHON) -m mypy
ALEMBIC      := cd backend && ../.venv/bin/alembic

ENV          ?= dev
TAG          ?= latest
ACR_NAME     ?= investorinsightsacr

.PHONY: help setup install up down restart logs logs-api logs-worker \
        test test-unit test-integration test-e2e test-coverage \
        lint lint-fix format \
        migrate migrate-new migrate-rollback db-shell \
        seed reset \
        azure-login azure-deploy-dev azure-deploy-prod azure-seed-keyvault \
        azure-build-push azure-deploy-apps azure-migrate azure-logs \
        azure-destroy azure-cost \
        shell flower qdrant-dashboard clean

# ── Help ────────────────────────────────────────────────────
help:                               ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk \
		'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ── Local Development Setup ────────────────────────────────
setup:                              ## First-time local setup (.env, venv, deps, infra up, migrate)
	@echo "──── InvestorInsights local setup ────"
	cp -n .env.example .env 2>/dev/null || true
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt -r backend/requirements-dev.txt
	$(COMPOSE) up -d
	@echo "Waiting for services to start…"
	@sleep 5
	$(ALEMBIC) upgrade head
	@echo "✅ Setup complete. Run 'make up' to start services."

install:                            ## Install / update Python dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt -r backend/requirements-dev.txt

# ── Infrastructure (Docker) ────────────────────────────────
up:                                 ## Start local infra services (PG, Redis, Qdrant, Azurite)
	$(COMPOSE) up -d

down:                               ## Stop local infra services
	$(COMPOSE) down

restart:                            ## Restart local infra services
	$(COMPOSE) restart

logs:                               ## Tail logs for all infra services
	$(COMPOSE) logs -f --tail=100

# ── Database ───────────────────────────────────────────────
migrate:                            ## Run database migrations (alembic upgrade head)
	$(ALEMBIC) upgrade head

migrate-new:                        ## Create new migration (MESSAGE="description")
	$(ALEMBIC) revision --autogenerate -m "$(MESSAGE)"

migrate-rollback:                   ## Rollback last migration
	$(ALEMBIC) downgrade -1

db-shell:                           ## Open PostgreSQL shell
	$(COMPOSE) exec postgres psql -U analyst -d company_analysis

# ── Testing ────────────────────────────────────────────────
test:                               ## Run all tests (unit + integration)
	$(PYTEST) -v

test-unit:                          ## Run unit tests only
	$(PYTEST) backend/tests/unit -v

test-integration:                   ## Run integration tests only
	$(PYTEST) backend/tests/integration -v

test-e2e:                           ## Run end-to-end tests
	$(PYTEST) backend/tests/e2e -v --timeout=300

test-coverage:                      ## Run tests with coverage report
	$(PYTEST) --cov=backend/app --cov-report=html --cov-report=term --cov-fail-under=85 -v

# ── Code Quality ───────────────────────────────────────────
lint:                               ## Run linters (ruff check + mypy)
	$(RUFF) check backend/app/ backend/tests/
	$(RUFF) format --check backend/app/ backend/tests/
	$(MYPY) backend/app/ --strict

lint-fix:                           ## Auto-fix linting issues
	$(RUFF) check --fix backend/app/ backend/tests/
	$(RUFF) format backend/app/ backend/tests/

format:                             ## Format code with ruff
	$(RUFF) format backend/app/ backend/tests/

# ── Data & Operations ─────────────────────────────────────
seed:                               ## Seed default data (analysis profile, etc.)
	./scripts/seed.sh

reset:                              ## ⚠️  Wipe ALL local data and rebuild (dev only)
	$(COMPOSE) down -v
	$(COMPOSE) up -d
	@sleep 5
	$(MAKE) migrate
	$(MAKE) seed
	@echo "✅ Local environment reset."

# ── Run Server ─────────────────────────────────────────────
dev:                                ## Start the API server locally (uvicorn, reload)
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend

# ── Azure Infrastructure ──────────────────────────────────
azure-login:                        ## Login to Azure CLI
	az login
	az account set --subscription $${AZURE_SUBSCRIPTION_ID}

azure-deploy-dev:                   ## Deploy Azure infra (dev — budget ≤ $50/mo)
	cd infra && az deployment sub create \
		--location eastus2 \
		--template-file main.bicep \
		--parameters parameters/dev.bicepparam

azure-deploy-prod:                  ## Deploy Azure infra (production)
	cd infra && az deployment sub create \
		--location eastus2 \
		--template-file main.bicep \
		--parameters parameters/prod.bicepparam

azure-seed-keyvault:                ## Populate Key Vault with secrets
	./infra/scripts/seed-keyvault.sh $(ENV)

azure-build-push:                   ## Build and push Docker images to ACR
	az acr login --name $(ACR_NAME)
	docker build -t $(ACR_NAME).azurecr.io/investorinsights-api:$(TAG) ./backend
	docker build -t $(ACR_NAME).azurecr.io/investorinsights-frontend:$(TAG) ./frontend
	docker push $(ACR_NAME).azurecr.io/investorinsights-api:$(TAG)
	docker push $(ACR_NAME).azurecr.io/investorinsights-frontend:$(TAG)

azure-deploy-apps:                  ## Deploy Container Apps with latest images
	az containerapp update --name api \
		--resource-group rg-investorinsights-$(ENV) \
		--image $(ACR_NAME).azurecr.io/investorinsights-api:$(TAG)
	az containerapp update --name worker \
		--resource-group rg-investorinsights-$(ENV) \
		--image $(ACR_NAME).azurecr.io/investorinsights-api:$(TAG)
	az containerapp update --name frontend \
		--resource-group rg-investorinsights-$(ENV) \
		--image $(ACR_NAME).azurecr.io/investorinsights-frontend:$(TAG)

azure-migrate:                      ## Run DB migrations against Azure PostgreSQL
	az containerapp exec --name api \
		--resource-group rg-investorinsights-$(ENV) \
		--command "alembic upgrade head"

azure-logs:                         ## Stream Azure Container App logs
	az containerapp logs show --name api \
		--resource-group rg-investorinsights-$(ENV) --follow

azure-destroy:                      ## ⚠️  Destroy Azure environment (requires confirmation)
	./infra/scripts/destroy.sh $(ENV)

azure-cost:                         ## Show current Azure spend for resource group
	az consumption usage list \
		--start-date $$(date -v-30d +%Y-%m-%d) --end-date $$(date +%Y-%m-%d) \
		--query "[?contains(instanceName,'investorinsights')].{Name:instanceName, Cost:pretaxCost, Currency:currency}" \
		--output table
	@echo ""
	@echo "Dev budget target: ≤ $$50/month"

# ── Debugging ──────────────────────────────────────────────
shell:                              ## Open Python shell with app context
	$(PYTHON) -c "from app.config import get_settings; print('Settings loaded'); import code; code.interact(local=locals())"

flower:                             ## Open Celery Flower (task monitor)
	@echo "Flower UI: http://localhost:5555"
	$(COMPOSE) --profile monitoring up -d worker-monitor 2>/dev/null || \
		$(PYTHON) -m celery -A app.worker.celery_app flower --port=5555

qdrant-dashboard:                   ## Show Qdrant dashboard URL
	@echo "Qdrant Dashboard: http://localhost:6333/dashboard"

# ── Cleanup ────────────────────────────────────────────────
clean:                              ## Remove build artifacts, caches, compiled files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
	rm -rf backend/.pytest_cache backend/.mypy_cache
	@echo "✅ Cleaned."
