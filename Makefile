# ═══════════════════════════════════════════════════════════
#  Aegis — Production AI Agent for Customer Support
#  One-command development workflow
# ═══════════════════════════════════════════════════════════

.DEFAULT_GOAL := help

# ── Stack ──────────────────────────────────────────────────

.PHONY: up down restart logs clean db-reset

up: ## 🚀 Start the full stack (backend + frontend + redis)
	docker compose up --build

down: ## 🛑 Stop stack and remove images + dangling layers
	docker compose down -v --rmi local
	docker image prune -f

restart: ## 🔄 Restart the full stack (preserves DB state)
	docker compose down
	docker compose up --build

logs: ## 📋 Tail backend logs (use: make logs s=frontend)
	docker compose logs -f $(or $(s),backend)

clean: ## 🧹 Nuclear clean — remove everything including base images
	docker compose down -v --rmi all
	docker image prune -f

db-reset: ## 🗄️  Reset & reseed the Supabase database (requires SUPABASE_MANAGEMENT_KEY in backend/.env)
	node scripts/db-reset.mjs

# ── Testing ────────────────────────────────────────────────

.PHONY: test test-backend test-frontend lint

test: test-backend test-frontend ## ✅ Run all tests

test-backend: ## 🐍 Run backend tests with coverage (100% required)
	cd backend && python -m pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-fail-under=100 -v

test-frontend: ## ⚛️  Run frontend tests with Vitest
	cd frontend && npm test -- --coverage

lint: ## 🔍 Lint backend (ruff) + frontend (eslint)
	ruff check backend/
	cd frontend && npm run lint

# ── Screenshots & Videos ──────────────────────────────────

.PHONY: screenshots demo clips

screenshots: ## 📸 Capture all 24 UI screenshots (requires stack running)
	node scripts/capture-screenshots.mjs

# Individual screenshot targets for development
ss-dashboard:          ## 📸 shot 01: dashboard
	node scripts/capture-screenshots.mjs dashboard
ss-refund:             ## 📸 shot 02: refund HITL suite (thinking → modal → deny → approve)
	node scripts/capture-screenshots.mjs refund-hitl
ss-technical:          ## 📸 shot 03: technical HITL suite
	node scripts/capture-screenshots.mjs technical-hitl
ss-billing:            ## 📸 shot 04: billing resolution
	node scripts/capture-screenshots.mjs billing-resolution
ss-upgrade:            ## 📸 shot 05: upgrade HITL suite
	node scripts/capture-screenshots.mjs upgrade-resolution
ss-reactivate:         ## 📸 shot 06: reactivate resolution
	node scripts/capture-screenshots.mjs reactivate-resolution
ss-suspend:            ## 📸 shot 07: suspend HITL suite
	node scripts/capture-screenshots.mjs suspend-hitl
ss-cache:              ## 📸 shot 08: semantic cache hit
	node scripts/capture-screenshots.mjs cache-hit
ss-edge:               ## 📸 shots 09-13: all edge cases
	node scripts/capture-screenshots.mjs edge-notfound edge-mismatch edge-typo edge-nameonly edge-cancelled
ss-metrics:            ## 📸 shot 14: observability metrics
	node scripts/capture-screenshots.mjs metrics
ss-traces:             ## 📸 shot 15: LangSmith traces
	node scripts/capture-screenshots.mjs traces
ss-tickets:            ## 📸 shot 16: recent tickets
	node scripts/capture-screenshots.mjs recent-tickets
ss-recent-tickets: ss-tickets ## 📸 alias for ss-tickets
ss-database:           ## 📸 shot 17: database explorer
	node scripts/capture-screenshots.mjs database

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
