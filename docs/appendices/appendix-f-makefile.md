# Appendix F: Makefile Commands

> Referenced from [System Specification](../system_specification.md)

```makefile
# Makefile — Common commands for development and operations

.PHONY: help setup up down logs test lint migrate seed backup

help:                               ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk \
		'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local Development Setup ─────────────────────────────────
setup:                              ## First-time local setup (copy .env, build images)
	cp -n .env.example .env || true
	docker compose -f docker-compose.dev.yml build
	docker compose -f docker-compose.dev.yml run --rm api alembic upgrade head
	docker compose -f docker-compose.dev.yml run --rm api python -m app.scripts.seed_defaults

up:                                 ## Start all local dev services
	docker compose -f docker-compose.dev.yml up -d

down:                               ## Stop all local dev services
	docker compose -f docker-compose.dev.yml down

restart:                            ## Restart all local dev services
	docker compose -f docker-compose.dev.yml restart

logs:                               ## Tail logs for all services
	docker compose -f docker-compose.dev.yml logs -f --tail=100

logs-api:                           ## Tail API logs
	docker compose -f docker-compose.dev.yml logs -f --tail=100 api

logs-worker:                        ## Tail worker logs
	docker compose -f docker-compose.dev.yml logs -f --tail=100 worker

# ── Database ────────────────────────────────────────────────
migrate:                            ## Run database migrations
	docker compose -f docker-compose.dev.yml run --rm api alembic upgrade head

migrate-new:                        ## Create new migration (pass MESSAGE="description")
	docker compose -f docker-compose.dev.yml run --rm api alembic revision --autogenerate -m "$(MESSAGE)"

migrate-rollback:                   ## Rollback last migration
	docker compose -f docker-compose.dev.yml run --rm api alembic downgrade -1

db-shell:                           ## Open PostgreSQL shell
	docker compose -f docker-compose.dev.yml exec postgres psql -U analyst -d company_analysis

# ── Testing ─────────────────────────────────────────────────
test:                               ## Run all tests (unit + integration)
	docker compose -f docker-compose.dev.yml run --rm api pytest tests/unit tests/integration -v

test-unit:                          ## Run unit tests only
	docker compose -f docker-compose.dev.yml run --rm api pytest tests/unit -v

test-integration:                   ## Run integration tests only
	docker compose -f docker-compose.dev.yml run --rm api pytest tests/integration -v

test-e2e:                           ## Run end-to-end tests
	docker compose -f docker-compose.dev.yml run --rm api pytest tests/e2e -v --timeout=300

test-coverage:                      ## Run tests with coverage report
	docker compose -f docker-compose.dev.yml run --rm api pytest tests/unit tests/integration \
		--cov=app --cov-report=html --cov-report=term --cov-fail-under=85

test-frontend:                      ## Run frontend tests
	docker compose -f docker-compose.dev.yml run --rm frontend npm test

# ── Code Quality ────────────────────────────────────────────
lint:                               ## Run linters
	docker compose -f docker-compose.dev.yml run --rm api ruff check app/
	docker compose -f docker-compose.dev.yml run --rm api ruff format --check app/
	docker compose -f docker-compose.dev.yml run --rm api mypy app/ --strict

lint-fix:                           ## Auto-fix linting issues
	docker compose -f docker-compose.dev.yml run --rm api ruff check --fix app/
	docker compose -f docker-compose.dev.yml run --rm api ruff format app/

# ── Data & Operations ──────────────────────────────────────
seed:                               ## Seed default analysis profile
	docker compose -f docker-compose.dev.yml run --rm api python -m app.scripts.seed_defaults

reset:                              ## ⚠️  Wipe ALL local data (development only)
	docker compose -f docker-compose.dev.yml down -v
	docker compose -f docker-compose.dev.yml up -d
	sleep 5
	$(MAKE) migrate
	$(MAKE) seed

# ── Azure Infrastructure ───────────────────────────────────
azure-login:                        ## Login to Azure CLI
	az login
	az account set --subscription $(AZURE_SUBSCRIPTION_ID)

azure-deploy-dev:                   ## Deploy Azure infrastructure (dev — budget ≤ $50/mo)
	cd infra && az deployment sub create \
		--location eastus2 \
		--template-file main.bicep \
		--parameters parameters/dev.bicepparam

azure-deploy-prod:                  ## Deploy Azure infrastructure (prod environment)
	cd infra && az deployment sub create \
		--location eastus2 \
		--template-file main.bicep \
		--parameters parameters/prod.bicepparam

azure-seed-keyvault:                ## Populate Key Vault with initial secrets
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

azure-cost:                         ## Show current Azure spend for the resource group
	az consumption usage list \
		--start-date $$(date -v-30d +%Y-%m-%d) --end-date $$(date +%Y-%m-%d) \
		--query "[?contains(instanceName,'investorinsights')].{Name:instanceName, Cost:pretaxCost, Currency:currency}" \
		--output table
	@echo ""
	@echo "Dev budget target: ≤ $$50/month"
	@echo "Run 'az cost management' in Azure Portal for detailed breakdown."

# ── Debugging ──────────────────────────────────────────────
shell:                              ## Open Python shell in API container
	docker compose -f docker-compose.dev.yml run --rm api python

flower:                             ## Open Celery Flower (task monitor) — local dev
	@echo "Flower UI: http://localhost:5555"
	docker compose -f docker-compose.dev.yml --profile monitoring up -d worker-monitor

qdrant-dashboard:                   ## Show Qdrant dashboard URL
	@echo "Qdrant Dashboard: http://localhost:6333/dashboard"
```
