.PHONY: help up down restart logs ps build rebuild test lint format smoke storage-smoke embed-smoke chat-smoke eval eval-seed psql clean migrate migrate-down migrate-status migrate-new

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start all services in the background
	docker compose up -d
	@echo ""
	@echo "  Frontend:  http://localhost:5173"
	@echo "  API:       http://localhost:8000"
	@echo "  API docs:  http://localhost:8000/docs"

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Tail logs from all services
	docker compose logs -f --tail=200

ps: ## Show running services
	docker compose ps

build: ## Build service images
	docker compose build

rebuild: ## Rebuild service images without cache
	docker compose build --no-cache

test: ## Run backend tests inside the api container
	docker compose exec api uv run pytest -v

lint: ## Run linters
	cd backend && uv run ruff check app tests
	cd frontend && npm run lint

format: ## Auto-format code
	cd backend && uv run ruff format app tests scripts && uv run ruff check --fix app tests scripts

smoke: ## Verify Bedrock connectivity (requires AWS creds in .env)
	docker compose exec api uv run python scripts/bedrock_smoke_test.py

storage-smoke: ## Round-trip test against the object store (MinIO/S3)
	docker compose exec api uv run python scripts/storage_smoke_test.py

embed-smoke: ## Verify the configured embedding provider works (downloads ~1.3GB on first run)
	docker compose exec api uv run python scripts/embedding_smoke_test.py

chat-smoke: ## End-to-end chat against the running API (usage: make chat-smoke Q="your question")
	docker compose exec api uv run python scripts/chat_smoke_test.py "$(Q)"

eval-seed: ## Wipe documents and re-seed with sample_docs/ for a clean eval baseline
	docker compose exec api uv run python /app/evals/seed.py

eval: ## Run the golden Q&A set and write a report (usage: make eval LABEL=baseline TOPK=5)
	docker compose exec api uv run python /app/evals/run_eval.py \
		--label "$(or $(LABEL),baseline)" \
		--top-k "$(or $(TOPK),5)"

psql: ## Open a psql shell into the local database
	docker compose exec db psql -U eka -d eka

migrate: ## Apply all pending database migrations
	docker compose exec api uv run alembic upgrade head

migrate-down: ## Roll back the most recent migration
	docker compose exec api uv run alembic downgrade -1

migrate-status: ## Show current migration revision and history
	docker compose exec api uv run alembic current
	docker compose exec api uv run alembic history

migrate-new: ## Generate a new migration from model changes (usage: make migrate-new MSG="add foo column")
	docker compose exec api uv run alembic revision --autogenerate -m "$(MSG)"

clean: ## Remove containers, volumes, and caches
	docker compose down -v
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -prune -exec rm -rf {} + 2>/dev/null || true
