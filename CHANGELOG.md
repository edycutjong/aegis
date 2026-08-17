# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0](https://github.com/edycutjong/aegis/compare/v1.5.3...v2.0.0) (2026-08-17)


### ⚠ BREAKING CHANGES

* `reactivate` no longer auto-approves. Reactivating a suspended or cancelled account undoes a compliance action and resumes billing, so it is a real account-state change and now pauses at the human gate like every other mutating action. Only `resolve` completes autonomously.

### ✨ Features

* **frontend:** redesign dashboard around the approval gate ([a9126c2](https://github.com/edycutjong/aegis/commit/a9126c2cabc9105e9f4fca57f9f1c5e738ed4bba))
* require human approval for account reactivation ([96e87ab](https://github.com/edycutjong/aegis/commit/96e87aba60ea13335b5bc6a522add9a317e4a78f))


### 🐛 Bug Fixes

* **ci:** match release-please tags to the existing v* convention ([282aa9d](https://github.com/edycutjong/aegis/commit/282aa9da9d442fa2fe7eb7515b66567645330b95))
* **deps:** bump vitest to 4.1.10 (CVE-2026-47429, critical) ([1c8dd30](https://github.com/edycutjong/aegis/commit/1c8dd30193afdf896589bf96eee54698b3c80a05))
* **deps:** resolve 112 dependency vulnerabilities via lockfile ([2be99b3](https://github.com/edycutjong/aegis/commit/2be99b394db4b0795a235de34814d39572d238d6))
* replace decommissioned Groq models ([8721711](https://github.com/edycutjong/aegis/commit/87217112121e620ee98fc743e0254c5572f97146))


### 🧪 Tests

* add exhaustive safety invariants ([98e7115](https://github.com/edycutjong/aegis/commit/98e711548ab6c7aa548e2327a95bfcf29e1bd27a))
* add Playwright E2E infrastructure ([f7d1b98](https://github.com/edycutjong/aegis/commit/f7d1b98e8bdda2363498142971d3aa62248ef1a5))
* expand unit coverage to every source module ([88ea8f1](https://github.com/edycutjong/aegis/commit/88ea8f19729c16b49b356e2e8d9662f38d11f0c5))


### 📚 Documentation

* add GitHub community health files ([a34c52c](https://github.com/edycutjong/aegis/commit/a34c52cd44b3d86241506cc3f52279f887c9198b))
* correct claims that no longer match the code ([5659a06](https://github.com/edycutjong/aegis/commit/5659a063fc9cdbeedcd47d66b08254a0cdb09bc4))


### 📦 Build System

* add release-please semantic versioning ([d0b2f32](https://github.com/edycutjong/aegis/commit/d0b2f32f8451ab24de1ecce561483df80c2fac0a))
* add tooling targets, scripts, and social metadata ([24e2f35](https://github.com/edycutjong/aegis/commit/24e2f355b206d59c3e3bdafcb065e6ae41272660))


### 🔁 CI/CD

* add CodeQL, gitleaks, and Dependabot configuration ([cea51fe](https://github.com/edycutjong/aegis/commit/cea51fe0a7f3382a9bf20143b88e935873f4e21e))
* restructure pipeline into five gated stages ([fa30274](https://github.com/edycutjong/aegis/commit/fa30274a9f1d387763e63691a610437742604a55))

## [1.1.3] - 2026-03-05

### Added

- **Case Study Link** — Added the link to the devfolio portfolio page in the `README.md`
- **100% Test Coverage** — Added missing tests for invalid JSON edge cases and disabled LangSmith tracing

## [1.1.2] - 2026-03-05

### Changed

- Update classifier routing label from "Gemini 2.0 Flash" to "Gemini 2.5 Flash"
- Update MetricsPanel test fixtures to use current model names (`gpt-4.1`, `gpt-4.1-mini`, `gemini-2.5-flash`, `claude-sonnet-4-20250514`)

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

[1.1.3]: https://github.com/edycutjong/aegis/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/edycutjong/aegis/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/edycutjong/aegis/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/edycutjong/aegis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/edycutjong/aegis/releases/tag/v1.0.0
