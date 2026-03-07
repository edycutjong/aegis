# Release Notes: Aegis v1.2.0 🚀

This release introduces major observability improvements, perfect 100% test coverage across the entire stack, and automated Playwright scripts for high-fidelity demographic and screenshot generation.

## 🔭 Observability & UI
* **Real-time LangSmith Traces Panel:** Added a built-in tracing overlay in the dashboard (`TracesPanel.tsx`) that displays the full execution pipeline, latency, and token counts for every ticket.
* **Metrics Refinement:** Enhanced the `MetricsPanel` to accurately reflect model usage (Groq vs. Gemini/GPT) and track Human-in-the-Loop (HITL) wait times.
* **Database Explorer:** Added a visual database explorer to the dashboard for quick inspection of Supabase tables without leaving the app.

## 💯 Engineering Excellence
* **100% Test Coverage:** Achieved and enforced 100% branch and statement coverage for both the **FastAPI backend** (pytest) and **Next.js frontend** (Vitest + React Testing Library).
* **Self-Healing SQL & Retry Resilience:** Added robust test coverage for the 429 rate limit retry mechanisms and child-run model extraction logic (`get_top_level_child`).

## 🎬 Automated Media Generation
* **Comprehensive Screenshot Automation:** Introduced `capture-screenshots.mjs` (Playwright) to autonomously generate 24 high-resolution screenshots covering every state of the app (all ticket types, HITL approvals/denials, 5 edge cases, caching, metrics, and traces).
* **High-Fidelity Demo Recording:** Revamped `record-demo.mjs` and `record-clips.mjs` to simulate human-like typing (instead of instant clicks) for realistic video generation.
* **Expanded Scenario Coverage:** Added new automated recording scenes for complex edge cases: Name/ID Mismatch, Name-Only Lookup, and Cancelled Accounts.

## 📚 Documentation
* **Massive README Overhaul:** Completely rewrote the `README.md` to showcase the new capabilities. Includes 15 new screenshots demonstrating the real-time ThoughtStream, cache hits, dynamic model routing, and the 8 customer validation edge cases.
* **Video & Title Card Guides:** Added `VIDEO_GUIDE.md` and `TITLE_CARD_BRIEF.md` to standardize the production of portfolio assets.
