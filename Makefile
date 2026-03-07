# ═══════════════════════════════════════════════════════════
#  Aegis — Production AI Agent for Customer Support
#  One-command development workflow
# ═══════════════════════════════════════════════════════════

.DEFAULT_GOAL := help

# ── Stack ──────────────────────────────────────────────────

.PHONY: up down restart logs clean

up: ## 🚀 Start the full stack (backend + frontend + redis)
	docker compose up --build

down: ## 🛑 Stop stack and remove images + dangling layers
	docker compose down -v --rmi local
	docker image prune -f

restart: ## 🔄 Restart the full stack
	docker compose down
	docker compose up --build

logs: ## 📋 Tail backend logs (use: make logs s=frontend)
	docker compose logs -f $(or $(s),backend)

clean: ## 🧹 Nuclear clean — remove everything including base images
	docker compose down -v --rmi all
	docker image prune -f

# ── Testing ────────────────────────────────────────────────

.PHONY: test test-backend test-frontend lint

test: test-backend test-frontend ## ✅ Run all tests

test-backend: ## 🐍 Run backend tests with coverage (100% required)
	cd backend && python -m pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-fail-under=100 -v

test-frontend: ## ⚛️  Run frontend tests with Vitest
	cd frontend && npm test

lint: ## 🔍 Lint backend (ruff) + frontend (eslint)
	ruff check backend/
	cd frontend && npm run lint

# ── Screenshots & Videos ──────────────────────────────────

.PHONY: screenshots demo clips

screenshots: ## 📸 Capture all 21 UI screenshots (requires stack running)
	node scripts/capture-screenshots.mjs

demo: ## 🎬 Record full demo video (requires stack running)
	node scripts/record-demo.mjs

clips: ## 🎞️  Record individual feature clips (requires stack running)
	node scripts/record-clips.mjs

# ── Build & CI ────────────────────────────────────────────

.PHONY: build ci

build: ## 🏗️  Build Docker images (no cache)
	docker compose build --no-cache

ci: lint test build ## 🔁 Run full CI pipeline locally (lint → test → build)

# ── Help ──────────────────────────────────────────────────

.PHONY: help

help: ## 📖 Show available commands
	@echo ""
	@echo "  \033[1;36mAegis\033[0m — Production AI Agent for Customer Support"
	@echo "  ─────────────────────────────────────────────────"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36mmake %-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  \033[2mQuick start:  make up    →    make test    →    make screenshots\033[0m"
	@echo ""
