# MDHousingPolicyPipeline — common tasks.
# `make help` lists everything. Targets are thin wrappers over `uv run ...`.

.DEFAULT_GOAL := help
.PHONY: help install sync hooks lint format typecheck \
        test test-unit test-integration test-integration-keep test-plane-down check \
        db-up db-down up down build ingest serve docs-serve docs-build clean

# ---- setup ----------------------------------------------------------------
install sync: ## Resolve + install the uv workspace (single lockfile)
	uv sync

hooks: ## Install pre-commit git hooks (run once after clone)
	uv run pre-commit install

# ---- quality --------------------------------------------------------------
lint: ## Ruff lint (autofix)
	uv run ruff check --fix .

format: ## Ruff format the workspace
	uv run ruff format .

typecheck: ## Strict mypy across all packages
	uv run mypy src packages/*/src

# ---- tests ----------------------------------------------------------------
test: ## Run all tests (integration skips if pgvector is down)
	uv run pytest

test-unit: ## Fast unit tests only (no services)
	uv run pytest -m unit

test-integration: ## Integration tests against an ephemeral isolated test DB
	@echo "Bringing up ephemeral test plane (docker-compose.test.yml)..."
	docker compose -p mdhpp-test -f docker-compose.test.yml up -d
	@echo "Waiting for test pgvector to be healthy..."
	@until docker compose -p mdhpp-test -f docker-compose.test.yml \
		exec -T policy-db-test pg_isready -U mdhpp -d mdhpp_test >/dev/null 2>&1; do \
		sleep 1; \
	done
	@echo "Test DB ready. Running integration tests..."
	@trap 'docker compose -p mdhpp-test -f docker-compose.test.yml down -v' EXIT; \
		MDHPP_PG_HOST=localhost MDHPP_PG_PORT=5433 MDHPP_PG_DB=mdhpp_test \
		MDHPP_PG_USER=mdhpp MDHPP_PG_PASSWORD=mdhpp \
		uv run pytest -m integration

test-integration-keep: ## Same as test-integration but leaves the test DB running
	docker compose -p mdhpp-test -f docker-compose.test.yml up -d
	@until docker compose -p mdhpp-test -f docker-compose.test.yml \
		exec -T policy-db-test pg_isready -U mdhpp -d mdhpp_test >/dev/null 2>&1; do \
		sleep 1; \
	done
	MDHPP_PG_HOST=localhost MDHPP_PG_PORT=5433 MDHPP_PG_DB=mdhpp_test \
		MDHPP_PG_USER=mdhpp MDHPP_PG_PASSWORD=mdhpp \
		uv run pytest -m integration

test-plane-down: ## Tear down the ephemeral test plane (if left running)
	docker compose -p mdhpp-test -f docker-compose.test.yml down -v

# The gate CI runs: lint, format-check, types, unit. Run before pushing.
check: ## Full local gate: ruff + format-check + mypy + unit tests
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src packages/*/src
	uv run pytest -m unit

# ---- docker / data plane --------------------------------------------------
db-up: ## Start only pgvector (schema auto-applied on first boot)
	docker compose up -d policy-db

db-down: ## Stop pgvector
	docker compose stop policy-db

up: ## Start the full stack (app on http://localhost via nginx :80)
	docker compose up

down: ## Stop and remove the stack
	docker compose down

build: ## Rebuild the policy-api image
	docker compose build

# ---- app ------------------------------------------------------------------
ingest: ## Run the ingestion pipeline over corpus/ (Phase 2+)
	uv run mdhpp ingest

serve: ## Run the FastAPI app locally (Phase 3+)
	uv run mdhpp serve

# ---- docs ------------------------------------------------------------------
docs-serve: ## Serve the docs locally with live reload (http://localhost:8000)
	uv run --group docs mkdocs serve

docs-build: ## Build the static docs site into ./site
	uv run --group docs mkdocs build --strict

# ---- housekeeping ---------------------------------------------------------
clean: ## Remove caches and build artifacts (keeps the venv)
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache

# ---- help -----------------------------------------------------------------
# Self-documenting: prints every target whose line has a `## comment`.
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_ -]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
