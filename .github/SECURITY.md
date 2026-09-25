# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| latest (`main`) | ✅ |

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities. Instead,
report them privately:

- Email **edy.cu@live.com**, or
- Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) (Security → Report a vulnerability).

You'll get an acknowledgment within 48 hours and a resolution timeline after
triage. Please give us a reasonable window to patch before public disclosure.

## Security Model

Aegis lets an LLM generate SQL and propose account-mutating actions. The
defenses are described in the README (*Treat every LLM output as hostile
input*). The two boundaries below are covered by tests in
`backend/tests/test_safety_invariants.py`:

**1. The HITL approval gate.** Destructive actions (`refund`, `credit`,
`tier_change`, `suspend`, `reactivate`) never execute without an explicit human approval
resuming the LangGraph interrupt. The routing function `should_execute` is
tested for every action type and approval state: nothing unapproved reaches
`execute_action`.

**2. The table allowlist.** `GET /api/tables/{name}` serves only the four
seed-data tables in `ALLOWED_TABLES`. A permission-boundary test asserts that
path-traversal, catalog-table, and SQL-injection-shaped names are all rejected
with HTTP 400 before any query is built.

### Known limitations

Disclosed deliberately — see `README.md` → *Production Gaps*:

- **LLM-generated SQL can still be expensive.** `backend/app/db/sql_guard.py`
  parses every query with sqlglot (one `SELECT`, allowlisted tables and
  functions, no OID casts, rows capped), and the database runs it read-only as
  the `NOLOGIN` role `aegis_query` behind RLS. A recursive CTE or a large
  `string_agg` join is only bounded by the 5-second `statement_timeout`.
- **No authentication.** Every endpoint is unauthenticated. Aegis is a
  demonstration system; do not expose it to untrusted networks with real
  customer data.
- **"Verified customer" means matched, not authenticated.** The ID and name in
  the ticket text must match the database; nothing proves who wrote the
  ticket. The human approver is the real control.
- **Approval state is in-process.** `thread_store` and LangGraph's `MemorySaver`
  are per-process and non-durable; a restart loses pending approvals.

## Secrets

- No secrets are committed. `backend/.env` and `frontend/.env.local` are
  gitignored; only `.env.example` templates are tracked.
- CI scans every push and PR with **gitleaks** over full history
  (`fetch-depth: 0`) and **TruffleHog** for verified secrets.
- GitHub secret scanning and push protection are enabled on the repository.
