# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0](https://github.com/edycutjong/aegis/compare/v2.0.1...v2.1.0) (2026-09-25)


### ✨ Features

* expose Aegis as an A2A agent ([#46](https://github.com/edycutjong/aegis/issues/46)) ([1adbe39](https://github.com/edycutjong/aegis/commit/1adbe39f081362153145fc2100ac6995357d0a09))
* **frontend:** show backup-model answers in the trace; add the demo GIF ([#64](https://github.com/edycutjong/aegis/issues/64)) ([fbeaf13](https://github.com/edycutjong/aegis/commit/fbeaf131b418b9648c9e793eccf1997ce535bdad))
* **router:** run the chat steps on OpenAI, keep Groq for Prompt Guard and backup ([#53](https://github.com/edycutjong/aegis/issues/53)) ([0aa1b93](https://github.com/edycutjong/aegis/commit/0aa1b939cf562cf6016a5dbbbf8a7e2830c1ac77))


### 🐛 Bug Fixes

* address the external audit's day-1 findings ([#47](https://github.com/edycutjong/aegis/issues/47)) ([71c1bc3](https://github.com/edycutjong/aegis/commit/71c1bc3dc95f10f4daabf6c0e77da600e151db4d))
* **agent:** identify customers by company, flag hidden markup, never put emails in replies ([#62](https://github.com/edycutjong/aegis/issues/62)) ([68e8268](https://github.com/edycutjong/aegis/commit/68e826840a7189ff770fda01b9d2f5a5d9329aa6))
* **agent:** identify customers however the ticket names them; skip SQL for unidentified senders ([#55](https://github.com/edycutjong/aegis/issues/55)) ([dd1ed92](https://github.com/edycutjong/aegis/commit/dd1ed92adec667f6cd100f698c47b19b7fe09af7))
* **agent:** refunds only for money actually collected, inside the window, and not already returned ([#57](https://github.com/edycutjong/aegis/issues/57)) ([487799b](https://github.com/edycutjong/aegis/commit/487799b1e22a9de5ac351b3aa7e89e617ca37e63))
* **agent:** send duplicate-charge, security and "we did it" tickets to a person ([#51](https://github.com/edycutjong/aegis/issues/51)) ([a464911](https://github.com/edycutjong/aegis/commit/a4649119125cd94e13b0a1939169c655f6180dd5))
* **agent:** show the model the billing ledger with statuses; negated claims are not claims ([#58](https://github.com/edycutjong/aegis/issues/58)) ([ea9185c](https://github.com/edycutjong/aegis/commit/ea9185c81f11b315ff89439115f273d7237e4490))
* complete errored runs, derive test counts, remove the broken trace proxy ([#59](https://github.com/edycutjong/aegis/issues/59)) ([17ea46f](https://github.com/edycutjong/aegis/commit/17ea46f1bf7b18d3d4e9af3570a149dd9c2162d8))
* **frontend:** keep list semantics on the example-ticket panel ([#45](https://github.com/edycutjong/aegis/issues/45)) ([4b1e785](https://github.com/edycutjong/aegis/commit/4b1e78521d40b8c7a20e32153edd99b4630a0076))
* **frontend:** self-host fonts so builds never download them ([#63](https://github.com/edycutjong/aegis/issues/63)) ([18afc3c](https://github.com/edycutjong/aegis/commit/18afc3c3e8622e47e370b4fe1cf24c7aef1c49ed))
* **frontend:** shorten the meta description and add a CTA to the social card ([#44](https://github.com/edycutjong/aegis/issues/44)) ([7ba6003](https://github.com/edycutjong/aegis/commit/7ba6003a7d5b0d9081ca2f205e140f8c162decf1))
* resolve security and code-scanning alerts ([#39](https://github.com/edycutjong/aegis/issues/39)) ([89b675a](https://github.com/edycutjong/aegis/commit/89b675ac9cc79da22a484eada2c589b8377f05ce))
* **security:** mask public emails, stop trusting X-Forwarded-For, gate CI on security ([#48](https://github.com/edycutjong/aegis/issues/48)) ([3a322ea](https://github.com/edycutjong/aegis/commit/3a322ea2913026c92ae165849107f4dff471ddb4))


### ♻️ Refactoring

* make docs and comments match the code, delete dead code ([#49](https://github.com/edycutjong/aegis/issues/49)) ([44988ba](https://github.com/edycutjong/aegis/commit/44988ba7b19bb07b9d79d961ea6a696f5f65dc16))


### 🧪 Tests

* **evals:** add a blind held-out set v3, 72.8% with 2 safety violations ([#60](https://github.com/edycutjong/aegis/issues/60)) ([ec84fe9](https://github.com/edycutjong/aegis/commit/ec84fe905caa576c82dd1bdc636f18e70697a4c3))
* **evals:** add a fresh held-out set v2, 68.7% with 12 safety violations ([#56](https://github.com/edycutjong/aegis/issues/56)) ([c852ffb](https://github.com/edycutjong/aegis/commit/c852ffb391512b1ca19e4844866ad012b30091b6))
* **evals:** add a held-out ticket set and tighten loose expectations ([#50](https://github.com/edycutjong/aegis/issues/50)) ([98c861c](https://github.com/edycutjong/aegis/commit/98c861cdbb96a9e9fef30013215ac20af57920dd))
* **frontend:** give the receipt-retry test room on slow runners ([#54](https://github.com/edycutjong/aegis/issues/54)) ([6d1c106](https://github.com/edycutjong/aegis/commit/6d1c10660fab55adb690497f50b82d27976b9cdc))


### 📚 Documentation

* link the API docs at api.aegis.edycu.dev ([#42](https://github.com/edycutjong/aegis/issues/42)) ([b249dfe](https://github.com/edycutjong/aegis/commit/b249dfea2aaac1951784f0ff271191689656ce4b))
* move the live demo to aegis.edycu.dev ([#41](https://github.com/edycutjong/aegis/issues/41)) ([214b171](https://github.com/edycutjong/aegis/commit/214b1719fa59d51b4aa08631e181c7497cf3733d))
* state the new safety rules as pattern checks, allow the evals scope ([#52](https://github.com/edycutjong/aegis/issues/52)) ([f0d46e3](https://github.com/edycutjong/aegis/commit/f0d46e3557b4fe0845921556181348c067284854))


### 🔁 CI/CD

* let release-please tag releases on merge ([#43](https://github.com/edycutjong/aegis/issues/43)) ([6691bf0](https://github.com/edycutjong/aegis/commit/6691bf0fc80d0fb85608c206feb91b90ed7165e5))

## [2.0.1](https://github.com/edycutjong/aegis/compare/v2.0.0...v2.0.1) (2026-09-25)


### 🧪 Tests

* read the expected API version from version.txt ([6de6f91](https://github.com/edycutjong/aegis/commit/6de6f919fa274c12b00c6afb9c0541094d7d4264))


### 📚 Documentation

* state eval run-to-run variance next to the scorecard ([89c41e9](https://github.com/edycutjong/aegis/commit/89c41e9d3015fe0e269e48f9133cb56e16dcfe30))


### 📦 Build System

* **deps:** bump the actions group across 1 directory with 7 updates ([#35](https://github.com/edycutjong/aegis/issues/35)) ([9a281e5](https://github.com/edycutjong/aegis/commit/9a281e5ace2aed323ac92caf2c9d2203c738b0f7))
* **deps:** bump the minor-and-patch group across 1 directory with 14 updates ([#32](https://github.com/edycutjong/aegis/issues/32)) ([9e9e7f8](https://github.com/edycutjong/aegis/commit/9e9e7f8af6c36bfcf461326ae01171c947988a56))

## [2.0.0](https://github.com/edycutjong/aegis/compare/v1.5.3...v2.0.0) (2026-09-24)


### ⚠ BREAKING CHANGES

* `reactivate` no longer auto-approves. Reactivating a suspended or cancelled account undoes a compliance action and resumes billing, so it is a real account-state change and now pauses at the human gate like every other mutating action. Only `resolve` completes autonomously.

### ✨ Features

* **agent:** screen input for prompt injection and fix four eval-found defects ([b4cf5d1](https://github.com/edycutjong/aegis/commit/b4cf5d1c42377c340ae66311222925a9693d61db))
* **api:** protect the public demo's LLM spend ([618d6cd](https://github.com/edycutjong/aegis/commit/618d6cd460637156f69641fe7e6420c4b6799053))
* **api:** stream every SQL attempt and return sanitized errors ([99979cc](https://github.com/edycutjong/aegis/commit/99979ccc0c611529e608d8385b6a822dd4718b0c))
* **deploy:** production container and per-call LLM timeouts ([b547151](https://github.com/edycutjong/aegis/commit/b5471513dd7bb34d6adf14af90b5ef84f61090bd))
* **evals:** golden-set harness against real models, with a published scorecard ([9f61410](https://github.com/edycutjong/aegis/commit/9f6141044cf28e88f2eee73c055840eb24205054))
* **frontend:** private run receipts, OG card, honest traces drawer, a11y fixes ([e896369](https://github.com/edycutjong/aegis/commit/e89636979a7e34cc484708768878748c873f8a74))
* **frontend:** rebuild the dashboard around the pause a human releases ([84799cc](https://github.com/edycutjong/aegis/commit/84799cc075cc05076c8e6d1777089027e3ce500a))
* **frontend:** redesign dashboard around the approval gate ([a9126c2](https://github.com/edycutjong/aegis/commit/a9126c2cabc9105e9f4fca57f9f1c5e738ed4bba))
* require human approval for account reactivation ([96e87ab](https://github.com/edycutjong/aegis/commit/96e87aba60ea13335b5bc6a522add9a317e4a78f))
* **routing:** fail over across providers and attribute cost to the model that answered ([8161f59](https://github.com/edycutjong/aegis/commit/8161f590ab616877f0ae64815cddd4dc0780a6dc))
* **security:** confine LLM-written SQL to the four Aegis tables ([1f99e39](https://github.com/edycutjong/aegis/commit/1f99e394862976b5c6572487b0f747180e881708))


### 🐛 Bug Fixes

* **agent:** enforce action invariants on every path, including the shortcut ([b92dc2e](https://github.com/edycutjong/aegis/commit/b92dc2edfd8dd7b97626dcd3db076e188a85c845))
* **agent:** fetch billing evidence at validation; recognize a leading customer name ([8e1d6e1](https://github.com/edycutjong/aegis/commit/8e1d6e1e4d3ef25c69f4aed566e8ec09bb86b6f2))
* **agent:** stop ticket boilerplate from retrieving unrelated policies ([0003c2b](https://github.com/edycutjong/aegis/commit/0003c2b6a9a3b0a78c26f575024634cc8df08d12))
* **api:** server-generated thread ids, private receipts, no replayed approvals ([94141fb](https://github.com/edycutjong/aegis/commit/94141fb9b9595ae532e62446023e53a7d95d7d36))
* **ci:** match release-please tags to the existing v* convention ([282aa9d](https://github.com/edycutjong/aegis/commit/282aa9da9d442fa2fe7eb7515b66567645330b95))
* **deps:** bump vitest to 4.1.10 (CVE-2026-47429, critical) ([1c8dd30](https://github.com/edycutjong/aegis/commit/1c8dd30193afdf896589bf96eee54698b3c80a05))
* **deps:** resolve 112 dependency vulnerabilities via lockfile ([2be99b3](https://github.com/edycutjong/aegis/commit/2be99b394db4b0795a235de34814d39572d238d6))
* **frontend:** call the exact-match cache a response cache ([15537fa](https://github.com/edycutjong/aegis/commit/15537fad64faee4d5a1d8c70fc870011d8003e22))
* replace decommissioned Groq models ([8721711](https://github.com/edycutjong/aegis/commit/87217112121e620ee98fc743e0254c5572f97146))
* **security:** allowlist SQL functions; normalize and narrow the injection screen ([a0ec1c2](https://github.com/edycutjong/aegis/commit/a0ec1c21ad55ef464d57a9a7489a2a7c14ff2137))
* **security:** only the backend's secret key can run agent SQL, read-only ([c181f14](https://github.com/edycutjong/aegis/commit/c181f1471d1152c133960070754db3539ab3cdb7))


### 🧪 Tests

* add exhaustive safety invariants ([98e7115](https://github.com/edycutjong/aegis/commit/98e711548ab6c7aa548e2327a95bfcf29e1bd27a))
* add Playwright E2E infrastructure ([f7d1b98](https://github.com/edycutjong/aegis/commit/f7d1b98e8bdda2363498142971d3aa62248ef1a5))
* expand unit coverage to every source module ([88ea8f1](https://github.com/edycutjong/aegis/commit/88ea8f19729c16b49b356e2e8d9662f38d11f0c5))


### 📚 Documentation

* add GitHub community health files ([a34c52c](https://github.com/edycutjong/aegis/commit/a34c52cd44b3d86241506cc3f52279f887c9198b))
* correct claims that no longer match the code ([5659a06](https://github.com/edycutjong/aegis/commit/5659a063fc9cdbeedcd47d66b08254a0cdb09bc4))
* publish the final 3-trial scorecard (99.2% pass, 0 safety violations) ([0c03244](https://github.com/edycutjong/aegis/commit/0c032447569e954651237317ff8a06798f1684f8))
* re-capture README screenshots from the live deployment ([549515a](https://github.com/edycutjong/aegis/commit/549515ae793a60aaeb79c5e7f6e8d5387e923dcf))
* rewrite README around measured results, refresh screenshots, drop stale tooling ([8ac6755](https://github.com/edycutjong/aegis/commit/8ac6755058dd54b35c3d7a4d96742e68d89e1ff1))


### 📦 Build System

* add release-please semantic versioning ([d0b2f32](https://github.com/edycutjong/aegis/commit/d0b2f32f8451ab24de1ecce561483df80c2fac0a))
* add tooling targets, scripts, and social metadata ([24e2f35](https://github.com/edycutjong/aegis/commit/24e2f355b206d59c3e3bdafcb065e6ae41272660))
* **deps-dev:** bump browserslist from 4.28.1 to 4.28.9 in /frontend ([#25](https://github.com/edycutjong/aegis/issues/25)) ([50920d3](https://github.com/edycutjong/aegis/commit/50920d3c11c468e9ef1d1c082caff0dff3c3d4f7))
* **deps-dev:** bump js-yaml from 4.1.1 to 4.3.2 in /frontend ([#30](https://github.com/edycutjong/aegis/issues/30)) ([9d22ccb](https://github.com/edycutjong/aegis/commit/9d22ccb01335ab01d2dc7fb3d47cfd62683a1eb8))
* **deps-dev:** bump vitest from 4.1.10 to 4.1.11 in /frontend ([#28](https://github.com/edycutjong/aegis/issues/28)) ([ac3291a](https://github.com/edycutjong/aegis/commit/ac3291aa70d3234c006e1d91984d8fc146b27351))
* **deps:** bump baseline-browser-mapping in /frontend ([#26](https://github.com/edycutjong/aegis/issues/26)) ([7c6ad22](https://github.com/edycutjong/aegis/commit/7c6ad228b6d3124229a3932e459af25394b12a8a))
* **deps:** bump sharp and next in /frontend ([#29](https://github.com/edycutjong/aegis/issues/29)) ([10e8189](https://github.com/edycutjong/aegis/commit/10e8189972838b529fc53e0d5691116085d47f7a))
* **deps:** move to LangGraph 1.x, LangChain-core 1.x, FastAPI 0.141 ([47149c6](https://github.com/edycutjong/aegis/commit/47149c67e6ff4a00e5e41b29782c64457c666bd6))
* keep test tooling out of the production image; make mypy blocking ([238a644](https://github.com/edycutjong/aegis/commit/238a6442222c938dad5356fc787ae812e760509d))


### 🔁 CI/CD

* add CodeQL, gitleaks, and Dependabot configuration ([cea51fe](https://github.com/edycutjong/aegis/commit/cea51fe0a7f3382a9bf20143b88e935873f4e21e))
* make the security stage blocking; stop tests and evals tracing to LangSmith ([65a4360](https://github.com/edycutjong/aegis/commit/65a436054e18aa50608893af9a43516fa86db7ac))
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
