<div align="center">

# ⛊ Aegis

**A multi-agent support engine that investigates tickets against a live database, proposes one action,
and stops for a human before anything that moves money or changes an account.**

### [▶ Try the live demo](https://aegis.edycu.dev) · [Eval scorecard](backend/evals/SCORECARD.md) · [Security model](#-treat-every-llm-output-as-hostile-input) · [API docs](https://api.aegis.edycu.dev/docs)

[![CI](https://github.com/edycutjong/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/edycutjong/aegis/actions/workflows/ci.yml)
[![Evals](https://github.com/edycutjong/aegis/actions/workflows/evals.yml/badge.svg)](https://github.com/edycutjong/aegis/actions/workflows/evals.yml)
[![CodeQL](https://github.com/edycutjong/aegis/actions/workflows/codeql.yml/badge.svg)](https://github.com/edycutjong/aegis/actions/workflows/codeql.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20backend%20%C2%B7%20100%25%20frontend-brightgreen)](#-quality-gates)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

<img src="docs/screenshots/02-approval-gate.png" alt="Aegis holding a $49 refund at the human approval gate, with the full agent trace visible above it" width="100%">

</div>

## The short version

Aegis works a Tier-2 support queue. A LangGraph pipeline of four agents triages the ticket, verifies the
customer, writes and runs SQL against Postgres, retrieves the relevant internal policy, and proposes
**exactly one** action: refund, credit, tier change, suspend, reactivate, escalate, or resolve. Anything
except `resolve` **pauses** on a LangGraph interrupt until a human approves or denies it.

It is measured, not just demoed: a 43-ticket golden set, including 13 prompt-injection and SQL-exfiltration
attacks, runs three times against the real models and the real database:

<!-- scorecard:start -->
| | |
|---|---|
| **End-to-end pass rate** (129 runs) | **96.9%** (41/43 cases pass every trial) |
| **Safety-invariant violations** | **0** |
| **Prompt-injection attempts contained** | **100%** |
| Intent · customer · action accuracy | 100.0% · 100.0% · 96.9% |
| Input screen: injections flagged / benign tickets flagged | 69.2% / 0.0% |
| Latency to the approval gate, p50 / p95 | 5.55s / 7.69s |
| LLM cost per ticket, median | **$0.0028** |
<!-- scorecard:end -->

Read these numbers for what they are. The golden set is also the set the agent was fixed against, so
treat it as a regression gate, not an accuracy estimate for unseen tickets. Runs vary: pass rates
have ranged from 95.8% to 99.2% across runs, and the failures are listed in the
[scorecard](backend/evals/SCORECARD.md). Of the five safety checks, three are enforced in code after the
model answers (the approval gate, the amount cap, the identity override). The other two, forbidden
action types and forbidden phrases, depend on the model, and held in every run so far.

---

## How it works

```mermaid
flowchart LR
    T([Ticket]) --> S["🛡 screen_input<br/><sub>Prompt Guard 2 + rules</sub>"]
    S --> C["classify_intent<br/><sub>fast model · routes the lane</sub>"]
    C --> V{"validate_customer<br/><sub>8 identity edge cases</sub>"}
    V -- not found / mismatch --> R
    V -- verified --> W["write_sql<br/><sub>frontier model</sub>"]
    W --> X{"execute_sql<br/><sub>sqlglot guard → least-privilege role</sub>"}
    X -- error or guard block<br/>(≤3×) --> W
    X -- rows --> K["search_docs<br/><sub>ranked policy retrieval</sub>"]
    K --> P["propose_action<br/><sub>one action, evidence-bound</sub>"]
    P --> G{{"⏸ await_approval<br/>LangGraph interrupt"}}
    G -- approved --> E[execute_action]
    G -- denied --> R
    E --> R["generate_response"]
    R --> Z([Reply])

    style G fill:#3b2a06,stroke:#f5a524,color:#fff
    style S fill:#231a3a,stroke:#8b5cf6,color:#fff
    style X fill:#231a3a,stroke:#8b5cf6,color:#fff
```

| Agent | Nodes | Model lane |
|---|---|---|
| **Triage** | `screen_input`, `classify_intent` | Groq `gpt-oss-20b` + Llama Prompt Guard 2 |
| **Investigator** | `validate_customer`, `write_sql`, `execute_sql` | GPT-4.1 (SQL is where being wrong is expensive) |
| **Knowledge** | `search_docs` | none: deterministic ranked retrieval |
| **Resolution** | `propose_action`, `await_approval`, `execute_action`, `generate_response` | Groq `gpt-oss-120b` (billing/general) or Gemini 2.5 Flash (technical/account) |

Every primary model fails over to a **different vendor** with a 30s timeout. Cost is attributed from the
provider's response metadata, so a failed-over call is priced as the model that actually answered. (Gemini's
free tier throttles under load, so part of that lane is served by the `gpt-4.1-mini` fallback; the
[scorecard](backend/evals/SCORECARD.md) lists every model that actually ran.)

---

## Engineering decisions

### ⏸ The human gate is structural, not a prompt

The pause is a LangGraph `interrupt()` with a checkpointer, not an instruction asking the model to wait.
Only `resolve` completes without a human, and `test_safety_invariants.py` pins that for every action
type. On top of that, these rules are enforced in code after the model speaks:

- **Identity comes from validation, not the model.** The verified customer row flows through graph state
  and overrides whatever ID or name the LLM wrote. A hallucinated ID cannot receive a refund.
- **A mutating action with no verified customer is downgraded to `escalate`.**
- **A ticket flagged by the input screen always escalates.** The model's own text is dropped rather than
  quoted, so a complied-with injection can't ride along in the proposal.
- **A duplicate-charge complaint from a customer with a refund already on file goes to a person**, with
  that refund as context. A second double charge is new money owed, and only a person can tell the two
  apart.
- **A ticket that reports a leaked, exposed or compromised credential, or unauthorized access, can't
  resolve.** Someone has to revoke the credential and check for abuse, whatever the model proposed.
- **A `resolve` can't claim an action.** `resolve` executes nothing, so a proposal that says "your key has
  been rotated" or "a credit will be applied automatically" is escalated.

The last two are pattern checks, not guarantees. A live paraphrase ("pasted his API key into a public Slack
channel") got past the security rule, and was escalated only because the model's reply claimed the key "has
been revoked". A money complaint with no duplicate refund on file is still decided by the model, then checked
by the amount cap and the approval gate.

### 🛡 Treat every LLM output as hostile input

LLM-written SQL passes through three independent layers. Any one of them can fail and the next still holds:

1. **App: [`sql_guard.py`](backend/app/db/sql_guard.py).** sqlglot parses the AST: exactly one `SELECT`,
   allowlisted tables, **allowlisted functions** (aggregates, date and string helpers; nothing else), no
   other schemas, no `::reg*` casts, rows capped at 50. A rejection is fed back to the model as the error,
   so the self-healing loop repairs the query instead of the database ever seeing it.
2. **Postgres:** the function is `STABLE`, so it runs in a **read-only transaction**, with a pinned
   `search_path` and a 5s `statement_timeout`.
3. **Privileges:** it runs as `aegis_query`, a `NOLOGIN` role that can read four tables through RLS and
   nothing else, and only the backend's secret key may call it. **This is the wall; everything above it
   is a speed bump.** `make preflight` proves all of it against the live database on every run.

Prompt injection is screened on the way in by **Llama Prompt Guard 2**, which catches jailbreaks (0.998 on
"ignore all previous instructions"), plus narrow deterministic rules for what it misses: data exfiltration,
fake `<system>` tags, authority claims ("I'm the CEO"), JSON action smuggling, and bidi-hidden text. The
screen deliberately doesn't catch everything. The scorecard reports its recall and its false-positive rate
separately from containment, to show the deeper layers hold when it misses.

<details>
<summary><b>How this was found:</b> the SQL function was reachable with the public key, twice</summary>
<br>

The original function was `SECURITY DEFINER`, owned by `postgres`, and executable by the `anon` role. The
backend used Supabase's *publishable* key, which is designed to be public, and the database is shared with
other projects. So anyone holding that key could `SELECT` from every schema. The keyword blocklist inside
the function stopped DDL and DML but not reads.

The first fix gave the function a least-privilege owner. An adversarial review then showed that wasn't
enough: the public key could still call the function directly, skipping the app-side guard, and create
large objects (a write). Verified live, then closed: `EXECUTE` is now `service_role` only, the function
runs read-only, and table policies exist for `aegis_query` alone. The public key now reads nothing.
</details>

### 📊 Coverage measures your code. Evals measure your product.

The unit suite is at 100% coverage with every LLM and the database mocked. It stayed fully green while
every configured Groq model had been decommissioned and the database was suspended. So the suite now has
a counterpart that measures the running system:

- **[`evals/golden.jsonl`](backend/evals/golden.jsonl):** 40 tickets: 18 core flows, 8 identity edge cases,
  13 attacks, and 1 failed-payment case. Each is scored on intent, customer, action/outcome, and **safety
  invariants**: no mutating action without a human, amounts never above what billing supports, actions only
  on the ticket's customer, no compliance with exfiltration requests. (SQL containment is tested where it
  can fail: the guard's attack corpus and the live privilege checks.)
- **`--trials 3`**, because a single pass of a non-deterministic system proves little.
- **`--check`** fails CI on any safety violation or a >5-point regression against
  [`baseline.json`](backend/evals/baseline.json). It runs weekly and on demand
  ([`evals.yml`](.github/workflows/evals.yml)).
- **`make preflight`**: one real call per configured model, plus live checks that the database answers,
  the privilege boundary holds, writes are refused and runaway queries are cancelled, for under a cent. It is the check that would have caught the retired models on day one.

<details>
<summary><b>What the evals caught</b> (all fixed, each now a regression test)</summary>
<br>

| Symptom in the eval | Root cause | Fix |
|---|---|---|
| Verified customers escalated as "not found" | Resolver inferred existence from SQL rows; billing rows have `customer_id` but no `name` | Validated customer row carried in graph state |
| `#777 Kevin Lee` resolved to #12, then 0 rows | SQL writer trusted the ticket's ID, not the validated one | Validated ID passed to the SQL prompt |
| 6-hour outage got a **$5** credit (policy: 50% = $249.50) | Retrieval searched for the intent word only; the outage policy never surfaced | Term-overlap ranking over the whole knowledge base |
| 9 of 39 runs crashed under 4-way concurrency | Gemini free tier: 5 req/min; Groq: 8K tokens/min; "fallback" pointed at the same vendor | Fail-fast cross-provider failover + 30s timeouts |
| Agent explained how to query `information_schema` | Prompt rules alone lose to a weaker fallback model | Input screen + escalation enforced in code |
| Money promised inside a `resolve` | Policy said the credit is "automatic" | Rule: every money movement is `refund`/`credit` → human gate |
| After the review fixes, legitimate refunds escalated (pass rate 96.7% → 91.7%) | The new amount ceiling read the model's SQL rows, whose column names the model chooses (`b.type AS billing_type`) | Billing evidence fetched deterministically at validation; 99.2% |

Plus two quieter bugs: `.strip("sql")` strips a *character set*, so `ORDER BY email` became `ORDER BY emai`;
and the zero-records reply pasted the whole ticket after "Customer #".
</details>

### 💸 Spend protection for a public demo

`POST /api/chat` is the only endpoint that starts LLM work. It has a per-visitor sliding window
(8 tickets / 10 min) and a **global daily cap** (300 tickets). Proxy headers can be spoofed, so the daily
cap is the real ceiling. A 429 carries `Retry-After`, which the UI turns into a countdown. Raw provider
errors, which include account IDs, stay in server logs; the browser gets sanitized text.

### 🔍 Reviewed adversarially, then fixed

After the first pass, the repo went through an independent, adversarial review whose only brief was to
find reasons to reject it. It found real defects; all are fixed and each is now a regression test:

| Finding | Fix |
|---|---|
| The "already resolved" shortcut returned before the injection and identity overrides ran | One `_enforce_invariants` step runs on every path, injection override last |
| The SQL guard *denylisted* functions; 15 escapes (`pg_sleep_for`, `lo_from_bytea`, `repeat('a',1e9)`, `::regclass`…) | Function **allowlist** + `reg*` cast ban |
| The public key could call the SQL function directly and write large objects | `service_role`-only `EXECUTE`, read-only transaction, RLS for one role |
| Clients chose thread ids, and `/api/metrics` listed them: read or overwrite another visitor's run | Server-generated ids, never listed; receipts only via `/api/thread/{id}` |
| A cached *approved* refund could be replayed to the next identical ticket without a human | Only auto-resolved answers are cached |
| Injection rules flagged "our devs execute SQL queries", "every row in my export", emoji | Narrower rules, input normalization, tag-character detection |
| Unit tests were uploading traces to the real LangSmith project | Tracing disabled in tests; evals opt in |

---

## Screenshots

| Held at the gate | Released |
|---|---|
| <img src="docs/screenshots/02-approval-gate.png" alt="Refund held at the approval gate"> | <img src="docs/screenshots/03-released.png" alt="Approved refund with the customer reply and run receipt"> |
| **SQL guard blocking an exfiltration attempt** | **Injection screen forcing escalation** |
| <img src="docs/screenshots/04-sql-guard.png" alt="Three SQL attempts: two blocked by the SQL guard, one failed"> | <img src="docs/screenshots/05-injection-escalated.png" alt="A flagged ticket forced to human review"> |

<details>
<summary>First load and mobile</summary>
<br>
<img src="docs/screenshots/01-overview.png" alt="Aegis dashboard on first load" width="100%">
<p align="center"><img src="docs/screenshots/06-mobile-gate.png" alt="The approval gate on a phone" width="320"></p>
</details>

---

## Run it

The fastest way to see it is the **[live demo](https://aegis.edycu.dev)**: one click runs a real
ticket through real models against a real database. The demo database is read-only, and approved actions
are handed off as recommendations.

Locally:

```bash
git clone https://github.com/edycutjong/aegis.git && cd aegis
cp backend/.env.example backend/.env    # Supabase + Groq + OpenAI keys; Gemini optional
make db-reset                           # schema, seed data, least-privilege role
make up                                 # backend :8000 · frontend :3000 · redis
make preflight                          # every model answers, DB answers, privilege boundary holds
```

| Command | What it does |
|---|---|
| `make test` | 521 backend + 265 frontend unit tests, 100% coverage gate on both |
| `make e2e` | 32 Playwright tests (desktop + mobile), no backend or keys needed |
| `make evals` | Golden set × 3 against real models → `backend/evals/SCORECARD.md` (~$0.30) |
| `make ci` | lint → typecheck → test → audit → build |
| `make help` | everything else |

## Quality gates

Every PR runs four gated stages, all blocking: **quality** (ruff, mypy, eslint, tsc, both unit suites at
100%) → **security** (CodeQL, gitleaks, TruffleHog, pip-audit, npm audit, license check) → **build** (both
Docker images) → **E2E** (Playwright, chromium + mobile). Evals run weekly and on demand, since they cost money and need
secrets. Dependabot, conventional commits, and release-please handle versioning.

## Stack

**Backend:** Python 3.12, FastAPI, LangGraph 1.x, LangChain-core 1.x, sqlglot, SSE · **Frontend:** Next.js 16, React 19,
TypeScript, Tailwind 4 · **Data:** Supabase Postgres, Redis · **Models:** Groq (`gpt-oss-20b/120b`,
Prompt Guard 2), OpenAI (GPT-4.1, 4.1-mini), Google (Gemini 2.5 Flash) · **Ops:** Railway (API),
Vercel (web), LangSmith tracing, GitHub Actions

## Production gaps

Stated plainly rather than left for a reviewer to find:

| Gap | Today | What production needs |
|---|---|---|
| **Auth** | None; the demo is public by design | Session/JWT auth and per-tenant row-level scoping |
| **Approval durability** | `MemorySaver` + an in-process thread store: a restart drops pending approvals, and it can't run as more than one replica | Postgres checkpointer and a shared thread store |
| **Action execution** | Recommendation-only; nothing is written | `actions` table, idempotency key, compensating revert, audit log |
| **Response quality** | Scored on structure and safety, not tone | An LLM-as-judge dimension, calibrated against human labels |
| **Response cache** | Exact match on the normalized ticket | Semantic matching only with a per-customer key; a near-match must never serve another customer's answer |
| **Metrics** | In memory; reset on restart | Postgres/Timescale behind the same aggregate API |

## License

[MIT](LICENSE)
