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

screenshots: ## 📸 Capture all 24 UI screenshots (requires stack running)
	node scripts/capture-screenshots.mjs

# Individual screenshot targets for development
ss-dashboard:          ## 📸 1 shot: dashboard
	node scripts/capture-screenshots.mjs dashboard
ss-refund-hitl:        ## 📸 1 shot: refund HITL modal
	node scripts/capture-screenshots.mjs refund-hitl
ss-refund-approve:     ## 📸 1 shot: refund HITL approve
	node scripts/capture-screenshots.mjs refund-approve
ss-refund-deny:        ## 📸 1 shot: refund HITL deny
	node scripts/capture-screenshots.mjs refund-deny
ss-technical:          ## 📸 1 shot: technical resolution
	node scripts/capture-screenshots.mjs technical-resolution
ss-billing:            ## 📸 1 shot: billing resolution
	node scripts/capture-screenshots.mjs billing-resolution
ss-upgrade:            ## 📸 1 shot: upgrade resolution
	node scripts/capture-screenshots.mjs upgrade-resolution
ss-reactivate-hitl:    ## 📸 1 shot: reactivate HITL modal
	node scripts/capture-screenshots.mjs reactivate-hitl
ss-reactivate-approve: ## 📸 1 shot: reactivate HITL approve
	node scripts/capture-screenshots.mjs reactivate-approve
ss-reactivate-deny:    ## 📸 1 shot: reactivate HITL deny
	node scripts/capture-screenshots.mjs reactivate-deny
ss-suspend-hitl:       ## 📸 1 shot: suspend HITL modal
	node scripts/capture-screenshots.mjs suspend-hitl
ss-suspend-approve:    ## 📸 1 shot: suspend HITL approve
	node scripts/capture-screenshots.mjs suspend-approve
ss-suspend-deny:       ## 📸 1 shot: suspend HITL deny
	node scripts/capture-screenshots.mjs suspend-deny
ss-cache:              ## 📸 1 shot: semantic cache hit
	node scripts/capture-screenshots.mjs cache-hit
ss-edge:               ## 📸 5 shots: all edge cases
	node scripts/capture-screenshots.mjs edge-notfound edge-mismatch edge-typo edge-nameonly edge-cancelled
ss-metrics:            ## 📸 1 shot: observability metrics
	node scripts/capture-screenshots.mjs metrics
ss-traces:             ## 📸 1 shot: LangSmith traces
	node scripts/capture-screenshots.mjs traces
ss-tickets:            ## 📸 1 shot: recent tickets
	node scripts/capture-screenshots.mjs recent-tickets
ss-database:           ## 📸 1 shot: database explorer
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
