# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2026-03-05

### Changed

- Update classifier routing label from "Gemini 2.0 Flash" to "Gemini 2.5 Flash"
- Update MetricsPanel test fixtures to use current model names (`gpt-4.1`, `gpt-4.1-mini`, `gemini-2.5-flash`, `claude-sonnet-4-20250514`)

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

[1.1.2]: https://github.com/edycutjong/aegis/compare/v1.0.0...v1.1.2
[1.0.0]: https://github.com/edycutjong/aegis/releases/tag/v1.0.0
