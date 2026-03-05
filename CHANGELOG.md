# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-03-05

### Fixed

- **Dashboard Scroll** — Fix flex overflow in ThoughtStream with `min-h-0`, pin footer outside scroll area with `shrink-0`
- **Ticket History A11y** — Replace `<button>` with `<div role="button">` and add keyboard handler for Enter/Space
- **MetricsPanel Cleanup** — Remove redundant per-model detail bars, keep provider-level bar only

### Changed

- Restructure dashboard 3-column layout with customer disambiguator, fixed textarea/submit at bottom
- Footer now reads version dynamically from `package.json` instead of hardcoded string
- Simplify footer by moving thread ID to a tooltip

## [1.1.0] - 2026-03-05

### Added

- **Already-Resolved Detection** — Resolver agent now pre-checks billing data for existing refund/credit records, skipping unnecessary LLM calls when issues are already resolved
- **Robust JSON Parsing** — Action proposal parser now includes regex fallback to extract JSON from markdown-fenced LLM responses (`\`\`\`json ... \`\`\``)
- **dotenv Loading** — Backend config now loads `.env` files automatically for local (non-Docker) development
- **Redis URL Documentation** — `.env.example` now documents password-authenticated Redis URL format

### Changed

- Resolver tests expanded with 3 new test cases covering pre-check, no-refund fallback, and fenced-JSON parsing

## [1.0.0] - 2026-03-04

### Added

- **Multi-Agent Architecture** — 4 specialized agents (Triage, Investigator, Knowledge, Resolution) orchestrated via LangGraph
- **Human-in-the-Loop (HITL)** — Agent pauses for human approval before executing destructive actions (refunds, suspensions); non-destructive actions are auto-approved
- **Dynamic Model Routing** — Routes simple intents to Groq Llama-3.3 (~$0.00003/req) and complex intents to GPT-4.1/Gemini (~$0.008/req) with automatic fallback
- **Smart Customer Validation** — Handles 8 edge cases including fuzzy name matching, typo correction, disambiguation, and account status warnings
- **Self-Healing SQL** — Generates SQL from natural language with auto-retry up to 3× by feeding errors back to the LLM
- **Semantic Caching** — Redis-based deduplication serves identical queries in <50ms at $0.00 cost; failures are never cached
- **Real-time ThoughtStream** — Watch the agent's reasoning step-by-step via Server-Sent Events (SSE) with dual User/Dev modes
- **Observability Dashboard** — Track token usage, cost per request, cache hit ratio, model distribution, and database status in real-time
- **Ticket History** — Recent tickets persisted in localStorage with quick resubmission
- **Database Explorer** — View live counts of customers, billing records, support tickets, and internal docs
- **LangSmith Integration** — Full distributed tracing with node-level spans, LLM call tracking, and graph execution traces
- **Docker Compose** — One-command deployment for backend, frontend, and Redis
- **CI/CD Pipeline** — GitHub Actions with Ruff linting, pytest, ESLint, and Docker build verification
- **100% Test Coverage** — Backend (pytest + pytest-cov) and frontend (Vitest + React Testing Library) both at 100%

[1.1.1]: https://github.com/edycutjong/aegis/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/edycutjong/aegis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/edycutjong/aegis/releases/tag/v1.0.0
