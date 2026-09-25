# ═══════════════════════════════════════════════════════════
#  Aegis — Support engine with a human approval gate
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

.PHONY: test test-backend test-frontend test-safety lint lint-fix typecheck e2e e2e-ui audit security-scan

test: test-backend test-frontend ## ✅ Run all tests

test-backend: ## 🐍 Run backend tests with coverage (100% required)
	cd backend && python -m pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-fail-under=100 -v

test-frontend: ## ⚛️  Run frontend tests with Vitest
	cd frontend && npm test -- --coverage

test-safety: ## 🛡️  Run exhaustive safety-invariant tests (HITL gate + table allowlist)
	cd backend && python -m pytest tests/test_safety_invariants.py -v

lint: ## 🔍 Lint backend (ruff) + frontend (eslint)
	ruff check backend/
	cd frontend && npm run lint

lint-fix: ## 🩹 Auto-fix lint issues (ruff + eslint)
	ruff check --fix backend/
	cd frontend && npm run lint:fix

typecheck: ## 🔎 Type check backend (mypy) + frontend (tsc)
	cd backend && python -m mypy app --ignore-missing-imports
	cd frontend && npm run typecheck

# ── Live checks (real models + real DB; need backend/.env) ─

.PHONY: preflight evals evals-check

preflight: ## 🩺 One real call per model + DB + privilege boundary (~$0.001)
	cd backend && python -W ignore -m app.preflight

evals: ## 📊 Run the 43-case golden set x3 against real models → evals/SCORECARD.md (~$0.30)
	cd backend && python -W ignore -m evals.run --trials 3 --concurrency 3

evals-check: ## 🚦 Evals + fail on safety violation or >5pt regression vs baseline
	cd backend && python -W ignore -m evals.run --trials 3 --concurrency 3 --check

e2e: ## 🎭 Run Playwright E2E tests (no backend or API keys needed)
	cd frontend && npm run e2e

e2e-ui: ## 🎭 Run Playwright E2E tests in interactive UI mode
	cd frontend && npm run e2e:ui

audit: ## 🔐 Dependency CVE audit (pip-audit + npm audit)
	@echo "=== pip-audit (backend CVEs) ==="
	@python -m pip_audit -r backend/requirements.txt || true
	@echo ""
	@echo "=== npm audit (frontend) ==="
	@cd frontend && npm audit --audit-level=high || true

security-scan: audit ## 🔐 Full security sweep (deps + secrets in git history)
	@echo ""
	@echo "=== gitleaks (secrets in full history) ==="
	@gitleaks detect --no-banner --redact || true
	@echo ""
	@echo "=== license compliance (frontend) ==="
	@cd frontend && npx license-checker --production --failOn "GPL-3.0;AGPL-3.0" --summary || true

# ── Screenshots ───────────────────────────────────────────

.PHONY: screenshots

screenshots: ## 📸 README screenshots via real runs (BASE_URL=… for the live demo; default localhost:3000)
	node scripts/capture-screenshots.mjs

# ── Build & CI ────────────────────────────────────────────

.PHONY: build ci

build: ## 🏗️  Build Docker images (no cache)
	docker compose build --no-cache

ci: lint typecheck test audit build ## 🔁 Full CI pipeline locally (lint → typecheck → test → audit → build)

# ── Help ──────────────────────────────────────────────────

.PHONY: help

help: ## 📖 Show available commands
	@echo ""
	@echo "  \033[1;36mAegis\033[0m — Support engine with a human approval gate"
	@echo "  ─────────────────────────────────────────────────"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36mmake %-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  \033[2mQuick start:  make up    →    make test    →    make preflight    →    make evals\033[0m"
	@echo ""
