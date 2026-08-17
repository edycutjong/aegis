# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0](https://github.com/edycutjong/aegis/compare/aegis-v1.5.3...aegis-v2.0.0) (2026-08-17)


### ⚠ BREAKING CHANGES

* `reactivate` no longer auto-approves. Reactivating a suspended or cancelled account undoes a compliance action and resumes billing, so it is a real account-state change and now pauses at the human gate like every other mutating action. Only `resolve` completes autonomously.

### ✨ Features

* achieve 100% test coverage with new tests for agent nodes and observability, and update CI/README. ([abea9bb](https://github.com/edycutjong/aegis/commit/abea9bb3f1aeb4fc520977dd4bfa173b04e46094))
* add 3 HITL modal shots (refund/reactivate/suspend) — 21 → 24 total ([62b9c6c](https://github.com/edycutjong/aegis/commit/62b9c6c6b94c28d4a36ba875c78911961b49c31b))
* Add action hold and resume functionality with modal entrance/exit animations and UI refinements. ([f00a4af](https://github.com/edycutjong/aegis/commit/f00a4afc47deb1a426f09381d71fa087c68f11b3))
* Add agent type selection and configurable LLM parameters (model, temperature, top_p) to `AgentNode`. ([97849f0](https://github.com/edycutjong/aegis/commit/97849f021fd08d03c718aeaa043c205f760091d5))
* add already-resolved detection and robust JSON parsing to resolver ([1d11df0](https://github.com/edycutjong/aegis/commit/1d11df032b80745a3261f403ca3df2b171845a17))
* Add customer disambiguation logic and UI for improved ticket processing. ([cdcbda5](https://github.com/edycutjong/aegis/commit/cdcbda5cd29da307b8e8dcf2885e79017d12be2f))
* Add database status monitoring and semantic cache clearing functionality. ([63b7e30](https://github.com/edycutjong/aegis/commit/63b7e30f450905dbda7133caf75206e23a20a62d))
* add DEV mode screenshots + increase traces wait time ([ce2a640](https://github.com/edycutjong/aegis/commit/ce2a64064dff16208aada87ea1bff6e543b7237d))
* Add Groq integration and configure Llama-3 as the default fast model. ([314b1ff](https://github.com/edycutjong/aegis/commit/314b1ff460f10fb7bd750f280ab9d185e6494f6c))
* add Makefile for one-command development workflow ([f8dd099](https://github.com/edycutjong/aegis/commit/f8dd099e9ea9ea74b324cce35d4d9f1c5732f9ec))
* add screenshot capture script for README and case study assets ([a133d99](https://github.com/edycutjong/aegis/commit/a133d9914d67898da4ad24ad94f9c49f015866cb))
* Add scripts to test Langsmith run hierarchy and lineage retrieval. ([e80028f](https://github.com/edycutjong/aegis/commit/e80028f4462168d9644832210dfcad1fe9471152))
* add setup.sh and dev.sh convenience scripts ([d647d4c](https://github.com/edycutjong/aegis/commit/d647d4c808f2019eb8e9d476fd4764a5533a00bb))
* Add tests for error ticket history preview and Shift+Enter submission behavior, and refine test coverage exclusions. ([15a2d64](https://github.com/edycutjong/aegis/commit/15a2d6465f4b345bb4fbb757f1b1d9e90784d624))
* Add typing indicator to ThoughtStream, update thought step animation, and refactor dashboard grid styling. ([e963852](https://github.com/edycutjong/aegis/commit/e963852725b1435b3cd894bd6433839a79dcf60d))
* apply Supabase schema migration and seed data ([ad23037](https://github.com/edycutjong/aegis/commit/ad2303731526c951da4ce6ab92e33be1bdf9d1a7))
* auto-scroll Progress panel to latest step + 3 HITL modal shots ([9667b04](https://github.com/edycutjong/aegis/commit/9667b0444022db35c341a6b0d80ed3d329374516))
* conditionally show LangSmith Traces button based on tracing status ([0632e2a](https://github.com/edycutjong/aegis/commit/0632e2af04697895c68482f190c1c8dfa664a60b))
* Configure Vitest and add unit tests for frontend components, hooks, and API functions. ([e420207](https://github.com/edycutjong/aegis/commit/e420207289548160056c7307586ed72e0a3ac6ca))
* expand screenshot script to 21 shots — full feature coverage ([98d4368](https://github.com/edycutjong/aegis/commit/98d4368415b9c58e94eae4c608b306824eb181ed))
* **frontend:** redesign dashboard around the approval gate ([a9126c2](https://github.com/edycutjong/aegis/commit/a9126c2cabc9105e9f4fca57f9f1c5e738ed4bba))
* Implement a zero-records guard for SQL query results to directly generate a response when no data is found. ([bb2a818](https://github.com/edycutjong/aegis/commit/bb2a8184d3a08f20bf457fc1e6e912b69140fdf2))
* Implement database write operations for agent actions and auto-approve reactivate. ([9144800](https://github.com/edycutjong/aegis/commit/914480080e7bab761b6e0c5f0343c48f49f2e017))
* Implement intent-based model routing for agents and enhance model usage visualization in the metrics panel. ([d4b5f18](https://github.com/edycutjong/aegis/commit/d4b5f1834d73fe078e6fe8363dc339faabd1ea2e))
* Implement status bar, redesign final response UI, and style demo preset buttons. ([19fdcea](https://github.com/edycutjong/aegis/commit/19fdcead28f4c906b82f1d6be5299dc8b80e5812))
* Implement ticket history feature with local storage persistence and a new UI component. ([9ed4102](https://github.com/edycutjong/aegis/commit/9ed4102e9455928b3423b23af19c21c5088f430f))
* improve traces screenshots & swap DB/LangSmith layout ([cd1cdde](https://github.com/edycutjong/aegis/commit/cd1cdde02daa8cd0d67fb2e0c6d947c02ee63874))
* initial Aegis project scaffold ([e41169b](https://github.com/edycutjong/aegis/commit/e41169b19f372ffb29205413e5fd86c87d572f0e))
* Introduce a 'Hold' action for Human-in-the-Loop approvals, improve SQL keyword blocking, strip trailing semicolons from Supabase queries, and update the favicon. ([8391623](https://github.com/edycutjong/aegis/commit/8391623aa3ca66ad6770164fb29bd96e436c9a90))
* **observability:** add HITL timing, approval rate, and cache cost savings ([2f5be00](https://github.com/edycutjong/aegis/commit/2f5be00e49fca464dac84fe31b563437dcc15994))
* Refactor edge case clip recording to use a helper function with typed messages, add new edge cases, and include a database explorer clip. ([1a2de2c](https://github.com/edycutjong/aegis/commit/1a2de2c6d14957bab6c077d535e31c6775bccf80))
* require human approval for account reactivation ([96e87ab](https://github.com/edycutjong/aegis/commit/96e87aba60ea13335b5bc6a522add9a317e4a78f))
* resolve thoughtstream empty state and hitl metrics to 100% coverage ([8a808dc](https://github.com/edycutjong/aegis/commit/8a808dc3ea3297eb866001d4b76ce8a8a45bddcd))
* screenshot pipeline overhaul, DB reset script, README image remapping ([#12](https://github.com/edycutjong/aegis/issues/12)) ([1f44169](https://github.com/edycutjong/aegis/commit/1f441692e95b6aaacc79dbc6c4aa2c9dc721b210))
* **traces:** add LangSmith traces overlay with async performance ([#2](https://github.com/edycutjong/aegis/issues/2)) ([1e48c36](https://github.com/edycutjong/aegis/commit/1e48c3675ec60b8c4226309e604950591c74110d))
* **ui:** add AnimatedNumber and refine ThoughtStream, MetricsPanel, dashboard ([dba1417](https://github.com/edycutjong/aegis/commit/dba1417e0ce38b1aa853292cb00c7a3ccfc4f9dc))
* update demo tickets with common production scenarios and delete package-lock.json. ([6ad9748](https://github.com/edycutjong/aegis/commit/6ad9748e131195cfc9048fe9587e2fdb409d9dfe))
* update system architecture diagram to clarify cache interaction, model routing, and human-in-the-loop approval flow. ([023eedc](https://github.com/edycutjong/aegis/commit/023eedce92c914e34d8191007de880ab8525e4ad))
* **video:** add demo recording script, video guide, and gitignore rules ([b9627a8](https://github.com/edycutjong/aegis/commit/b9627a82681fa39056f085748c6ef055bceed99d))


### 🐛 Bug Fixes

* achieve 100% frontend branch coverage ([7e5bbca](https://github.com/edycutjong/aegis/commit/7e5bbca0191179832d817fc4a4c778e409729588))
* add ESLint config so next lint runs non-interactively in CI ([6598208](https://github.com/edycutjong/aegis/commit/6598208e48f7205af645fdac50189f72b2c0f0d2))
* add retry/backoff for LangSmith 429 rate limits ([a99f415](https://github.com/edycutjong/aegis/commit/a99f4153caeec7e4e137d18eb0287d974b6f2e07))
* audit fixes for recording scripts ([857f3ef](https://github.com/edycutjong/aegis/commit/857f3ef89a44a1b400a10f715dfbf2b1e884c78c))
* **ci:** resolve ruff E402/W293 lint errors and align Python to 3.12 ([#5](https://github.com/edycutjong/aegis/issues/5)) ([d1d7395](https://github.com/edycutjong/aegis/commit/d1d739513843049f8a65d1f69576c7008e8345b4))
* **deps:** bump vitest to 4.1.10 (CVE-2026-47429, critical) ([1c8dd30](https://github.com/edycutjong/aegis/commit/1c8dd30193afdf896589bf96eee54698b3c80a05))
* **deps:** resolve 112 dependency vulnerabilities via lockfile ([2be99b3](https://github.com/edycutjong/aegis/commit/2be99b394db4b0795a235de34814d39572d238d6))
* docker-compose networking for Redis and frontend API URL ([f2bfa07](https://github.com/edycutjong/aegis/commit/f2bfa07bf75cacb63f9e8351b72cad79eadb5bbe))
* **docker:** add Redis healthcheck to prevent startup race condition ([#3](https://github.com/edycutjong/aegis/issues/3)) ([9a7242d](https://github.com/edycutjong/aegis/commit/9a7242d207bd2b936f7a537a0a616f67cf3941c1))
* enrich generate_response prompt with real state data & make seed.sql idempotent ([902c594](https://github.com/edycutjong/aegis/commit/902c594d8b6654376773ed81f76da52c72c2741f))
* expand ticket history accordion before taking screenshot ([137f0b1](https://github.com/edycutjong/aegis/commit/137f0b1b7f84c0d7db324608717ec8bd7f7210c1))
* **lint:** delete debug scripts, strip W293 from test_main.py ([a24f76b](https://github.com/edycutjong/aegis/commit/a24f76b00b70ec8b07fa8435f9a03e193458d449))
* **lint:** remove f-prefix from plain string literal in main.py (F541) ([48187b9](https://github.com/edycutjong/aegis/commit/48187b9c0ebc6345af2f3138ab2645f24580e2f7))
* **lint:** remove trailing whitespace from blank line in test_agent_nodes W293 ([3e5da0d](https://github.com/edycutjong/aegis/commit/3e5da0d24f5e8f0ffe63dae7e1d3e0d0b21b70f9))
* **lint:** remove trailing whitespace from blank lines in main.py (W293) ([5eeab8e](https://github.com/edycutjong/aegis/commit/5eeab8e3a7a0e0e59b15d889d8019ace47471cfc))
* **lint:** suppress react-hooks/exhaustive-deps on AnimatedNumber.tsx ([fe9055c](https://github.com/edycutjong/aegis/commit/fe9055c625d47e3fd9ab9e140995749bbfade650))
* **makefile:** sync all ss-* targets with actual SHOTS keys; remove dead sub-shots ([577b3f5](https://github.com/edycutjong/aegis/commit/577b3f52194a37f67b5efee57d2baa32179027bb))
* model usage labels stay on single line + add per-preset ss targets ([ee2fa79](https://github.com/edycutjong/aegis/commit/ee2fa795c8b902b6704dd5ef572090e16de76c26))
* refine dashboard layout, scroll behavior, and accessibility ([b12342c](https://github.com/edycutjong/aegis/commit/b12342ccbd6f0f08f6001f4da0fd882617de5464))
* replace decommissioned Groq models ([8721711](https://github.com/edycutjong/aegis/commit/87217112121e620ee98fc743e0254c5572f97146))
* replace deprecated gemini-2.0-flash with gemini-2.5-flash ([fca8321](https://github.com/edycutjong/aegis/commit/fca8321c9ef4e56d6babc99e61a56ad781552e24))
* replace deprecated GPT-4o with GPT-4.1, update Claude model IDs ([4d977c9](https://github.com/edycutjong/aegis/commit/4d977c9623089d40f3ce928583f6308334da8708))
* resolve CI annotation warnings (next/font migration, eslint config) ([6790eac](https://github.com/edycutjong/aegis/commit/6790eac72c690761b1f0ac4ba5de6ed213da8c91))
* **scripts:** generate a ticket before taking recent-tickets screenshot so history is populated and can expand ([92b639a](https://github.com/edycutjong/aegis/commit/92b639a12605fccd309912f149dec8a91b383910))
* **scripts:** use Reactivate preset for refund-hitl shots — Refund auto-resolves due to existing DB data ([719572f](https://github.com/edycutjong/aegis/commit/719572f056fb4521ec0b178588b761272b6eff2c))
* **scripts:** wait for HITL modal animation before capture; add ss-recent-tickets Makefile alias ([1dc2074](https://github.com/edycutjong/aegis/commit/1dc207469daf43ef35fedec7460043403b3194ff))
* **test:** add coverage for traces TTL cache hit path ([#7](https://github.com/edycutjong/aegis/issues/7)) ([1f9ad68](https://github.com/edycutjong/aegis/commit/1f9ad68c04615c080be847d4f9d351810d82ed12))
* **ui:** force model usage labels to single line with flex-nowrap and shrink-0 ([647f910](https://github.com/edycutjong/aegis/commit/647f91062a0626ff76da2a5b506cdcac659f8dd1))
* **ui:** improve model usage labels with flex-wrap and whitespace-nowrap ([#11](https://github.com/edycutjong/aegis/issues/11)) ([70821e5](https://github.com/edycutjong/aegis/commit/70821e56b2b58633c8095e16b643e95aa465aa0f))
* **ui:** keep model usage labels on single line, remove flex-wrap ([9e083de](https://github.com/edycutjong/aegis/commit/9e083de04d4dfa0dc3ea1133e1dccf8eeccdff2a))
* **ui:** remove duplicate typing-indicator dots during initial loading state ([7c6f1a9](https://github.com/edycutjong/aegis/commit/7c6f1a9cb3ff32bdb15c9cde14bab3bd59e8ca61))
* **ui:** restore typing-indicator animation in empty state while processing ([296485f](https://github.com/edycutjong/aegis/commit/296485f0cf822c5026fcf7653e38c9138f7eb5e1))
* **ui:** use inline styles for flex-nowrap to guarantee single-line model labels ([e88d4ae](https://github.com/edycutjong/aegis/commit/e88d4aebad9cf1ecffd205f4047a23f062ef0203))
* **ui:** use shrink-0 instead of flex-shrink-0 in TracesPanel ([02f9019](https://github.com/edycutjong/aegis/commit/02f9019245b4988858096c77a64c15e6a87e6a5b))


### ♻️ Refactoring

* Add `no cover` pragmas to lifespan startup print and yield statements. ([62e81cc](https://github.com/edycutjong/aegis/commit/62e81cc19e43c0791321ba68e2292a2f83d62973))
* add get_top_level_child lineage tracing for LLM run model extraction ([3cb2752](https://github.com/edycutjong/aegis/commit/3cb2752c6cd9cb89325872b2ad01888e766dad9f))
* Optimize `useState` initialization, update ESLint ignores, reorder a backend warning filter, and remove a redundant ESLint suppression comment. ([a462216](https://github.com/edycutjong/aegis/commit/a4622165ff2ccee3f1c2a014fed2817cb5c70dc1))
* remove unused `json` import from investigator agent. ([593f5d2](https://github.com/edycutjong/aegis/commit/593f5d2955d1a6750b8f91fd53bb1520cb046b2f))
* simplify and reorient the architecture flowchart in README.md from left-to-right to top-down. ([d78aaf0](https://github.com/edycutjong/aegis/commit/d78aaf014d51ee760eabf68c1ce5e84df52a7ba0))
* Update CI to output coverage summary to GitHub step summary and remove unused imports from `test_main.py`. ([869764d](https://github.com/edycutjong/aegis/commit/869764d78a78b327f29db18b09413d7b1e56f519))
* use Quick Test preset buttons instead of typing in screenshot script ([983d2d7](https://github.com/edycutjong/aegis/commit/983d2d77edfd08eb2e5a2ce09a77bd0cdac15613))


### 🧪 Tests

* Add comprehensive tests for error history, metrics panel, and input behavior, and refine coverage ignores. ([8eb9c23](https://github.com/edycutjong/aegis/commit/8eb9c2339022a34ad2f43b476f4bfac8b6c8b191))
* add comprehensive unit test suite for backend configuration, observability, agent nodes, semantic cache, and model router. ([6bfdc24](https://github.com/edycutjong/aegis/commit/6bfdc24e5c6785fc1c08c9955ce1a737175e3104))
* add coverage for 429 retry and child-run fallback ([11bc73c](https://github.com/edycutjong/aegis/commit/11bc73cc57a30813bccdf0fbc8781377179e1a83))
* add exhaustive safety invariants ([98e7115](https://github.com/edycutjong/aegis/commit/98e711548ab6c7aa548e2327a95bfcf29e1bd27a))
* Add new tests for main application, agent graph, semantic cache, and Supabase integration, and name the agent workflow. ([91504b1](https://github.com/edycutjong/aegis/commit/91504b10c924888cfd5283274f374b6ea41e5139))
* add Playwright E2E infrastructure ([f7d1b98](https://github.com/edycutjong/aegis/commit/f7d1b98e8bdda2363498142971d3aa62248ef1a5))
* cover get_top_level_child edge cases (orphan parent + cycle detection) ([be0a942](https://github.com/edycutjong/aegis/commit/be0a9429a7e40dc4045a2481ea1931821a4e9406))
* expand coverage for page, MetricsPanel, TicketHistory, TracesPanel, and api ([0d892d8](https://github.com/edycutjong/aegis/commit/0d892d8bc3e905de5f076690f061b5bee9769056))
* expand unit coverage to every source module ([88ea8f1](https://github.com/edycutjong/aegis/commit/88ea8f19729c16b49b356e2e8d9662f38d11f0c5))


### 📚 Documentation

* add 2 expanded LangSmith trace screenshots to README ([430854d](https://github.com/edycutjong/aegis/commit/430854d47fc6cabb361bee6585cc8d55d38b9b1f))
* add API key links to .env.example ([50a3128](https://github.com/edycutjong/aegis/commit/50a31283662068850f5e4648874058fb669029b7))
* add GitHub community health files ([a34c52c](https://github.com/edycutjong/aegis/commit/a34c52cd44b3d86241506cc3f52279f887c9198b))
* Add LangSmith tracing to the architecture diagram. ([1a159b5](https://github.com/edycutjong/aegis/commit/1a159b5c90ae10138dd29c3c95bfce180d08d489))
* Add Python, Next.js, and MIT License badges to README. ([5e7ca78](https://github.com/edycutjong/aegis/commit/5e7ca78609263c98900279c349319e42888237f7))
* add screenshots, CHANGELOG, and CONTRIBUTING for v1.0 release ([b10105a](https://github.com/edycutjong/aegis/commit/b10105a0e49078a868019bda65853bb06bc8702a))
* **assets:** add architecture diagram and LangSmith trace screenshot ([#4](https://github.com/edycutjong/aegis/issues/4)) ([d5650d9](https://github.com/edycutjong/aegis/commit/d5650d9bc05c85a43bd7ceff5ce6ca71f5177509))
* correct claims that no longer match the code ([5659a06](https://github.com/edycutjong/aegis/commit/5659a063fc9cdbeedcd47d66b08254a0cdb09bc4))
* expand README with detailed features, project structure, testing, and quick start, and remove an unused import from the investigator agent. ([a481f71](https://github.com/edycutjong/aegis/commit/a481f716b95edc54f1bd087a70bb5faec419ecdb))
* fix reactivate + suspend screenshots to full width (80% → 100%) ([9cc9b97](https://github.com/edycutjong/aegis/commit/9cc9b977a6b6ef60fde2011d8cf7b6d677c52416))
* generate comprehensive README and v1.2.0 release notes ([616f823](https://github.com/edycutjong/aegis/commit/616f823eebb17f7d3a06b6e10390fc9e3aebb415))
* **readme:** reorder manual startup to launch Redis first ([#6](https://github.com/edycutjong/aegis/issues/6)) ([3b504a9](https://github.com/edycutjong/aegis/commit/3b504a9f48938700c7353ddeda218fa21ec07bb5))
* **readme:** update Quick Start and Testing to use make commands; add Development Commands reference ([5919d00](https://github.com/edycutjong/aegis/commit/5919d00e79dbebabfb99796d3a1b852f05545b1e))
* refresh all screenshots with latest captures ([4857155](https://github.com/edycutjong/aegis/commit/48571558f1f52ee8eb2ea0aeb0b7751051b65f4f))
* reorder README for recruiter/CTO flow + sync record-clips with capture-screenshots ([02ff252](https://github.com/edycutjong/aegis/commit/02ff2523efc3577f7faad6f1d1d6d2e9f2f32df9))
* restore original curated screenshots for dashboard, completed, and approval modal ([a574511](https://github.com/edycutjong/aegis/commit/a57451195af7b0b4517d92a7c4cef43f72a2476f))
* update architecture diagram for clarity and refresh model versions in README. ([e97366b](https://github.com/edycutjong/aegis/commit/e97366ba934067478522d3a865ef80629b8575ef))
* update architecture diagram to Mermaid, refine API key prerequisites, and bump Node.js and Next.js versions. ([9e6e615](https://github.com/edycutjong/aegis/commit/9e6e61567196588ac2bf199437f7db8f16354c9e))
* update demo screenshots to 1920x1080 and add dashboard screenshot ([8eaa9ae](https://github.com/edycutjong/aegis/commit/8eaa9ae8ca57ab2dec98f023db229b8f87dbe5b0))
* update README screenshots to docs/screenshots/ + sync env vars ([7ed3678](https://github.com/edycutjong/aegis/commit/7ed3678d69a8d4ff0df93e3813bcbaaaa789a8be))
* Updating README with 100% test coverage stats ([6bab82c](https://github.com/edycutjong/aegis/commit/6bab82cfc9f975bc222118a836f1fd71f2dbc654))


### 📦 Build System

* add release-please semantic versioning ([d0b2f32](https://github.com/edycutjong/aegis/commit/d0b2f32f8451ab24de1ecce561483df80c2fac0a))
* add tooling targets, scripts, and social metadata ([24e2f35](https://github.com/edycutjong/aegis/commit/24e2f355b206d59c3e3bdafcb065e6ae41272660))


### 🔁 CI/CD

* add CodeQL, gitleaks, and Dependabot configuration ([cea51fe](https://github.com/edycutjong/aegis/commit/cea51fe0a7f3382a9bf20143b88e935873f4e21e))
* add coverage report to frontend test target ([7f58480](https://github.com/edycutjong/aegis/commit/7f5848059fed7185882ce57f4b4c2150b7c6d811))
* add GitHub Actions CI pipeline ([d79384d](https://github.com/edycutjong/aegis/commit/d79384d24cbf7525021956f362992ee8447ac7e3))
* add GitHub Actions pipeline, upgrade Next.js 16, fix lint & Docker build ([807bcf7](https://github.com/edycutjong/aegis/commit/807bcf7e00b32b1c4d0292d07e8986a280107d39))
* Implement pytest coverage reporting with a minimum threshold and remove unused test imports. ([c6b4680](https://github.com/edycutjong/aegis/commit/c6b46809636c3657e908593ca734d923abf4b3ab))
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
