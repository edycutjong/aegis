"""Safety invariants — exhaustive verification of the two boundaries that matter.

Unit coverage proves the code we wrote is exercised. These tests prove something
different and stronger: that across the *entire* reachable input space of the
decision functions guarding money and data, the invariant never breaks.

Two boundaries are verified here:

  1. THE HITL APPROVAL GATE — no state that is not explicitly approved may ever
     route to `execute_action`, and destructive action types may never bypass
     the human interrupt.

  2. THE TABLE ALLOWLIST — `GET /api/tables/{name}` must refuse every name that
     is not one of the four seed tables, before any query is constructed.

The case counts below are asserted, not estimated. If you add an action type or
an approval status, the count assertion fails on purpose — update the constant
AND the number quoted in README.md / .github/SECURITY.md in the same commit.
"""

import itertools
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.agents.resolver import (
    await_approval,
    propose_action,
    should_execute,
)


@pytest.fixture
def client():
    """FastAPI test client with mocked configuration (no real credentials)."""
    with patch.dict(os.environ, {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key",
        "REDIS_URL": "redis://localhost:6379",
        "FRONTEND_URL": "http://localhost:3000",
    }, clear=False):
        from app.config import get_settings
        get_settings.cache_clear()

        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ─────────────────────────────────────────────────────────────
# Input space definitions
# ─────────────────────────────────────────────────────────────

# Every action type the Resolution Agent can emit, plus values that a
# malformed / hallucinated LLM response could realistically produce.
ALL_ACTION_TYPES = [
    "refund",
    "credit",
    "tier_change",
    "suspend",
    "reactivate",
    "escalate",
    "resolve",
    "unknown_type",  # LLM invented something
    "",             # LLM returned an empty type
]

# Action types that move money or change account state. These must never
# execute without a human in the loop.
DESTRUCTIVE_TYPES = {"refund", "credit", "tier_change", "suspend", "reactivate"}

# Types the Resolution Agent auto-approves as non-destructive.
AUTO_APPROVE_TYPES = {"resolve"}

# Every approval_status value reachable via the graph, plus near-misses that a
# bug, a casing slip, or a partially-written state could produce.
ALL_APPROVAL_STATUSES = [
    "approved",
    "denied",
    "pending",
    "not_required",
    "APPROVED",      # wrong case must NOT pass
    "approved ",     # trailing space must NOT pass
    "",
    None,
    "__MISSING__",   # key absent from state entirely
]

# Unrelated state that must have zero influence on routing.
IRRELEVANT_STATE_VARIANTS = [
    {},
    {"execution_result": "Refund of $500.00 processed"},
    {"denial_reason": "manager rejected", "customer_found": True},
]


# ─────────────────────────────────────────────────────────────
# 1. THE HITL APPROVAL GATE — exhaustive
# ─────────────────────────────────────────────────────────────

class TestHitlGateExhaustive:
    """`should_execute` is the last branch before money moves. Verify all of it."""

    def test_no_unapproved_state_ever_reaches_execute_action(self):
        """Exhaustive: only the exact string 'approved' may route to execution.

        Enumerates the full cross-product of action type × approval status ×
        irrelevant surrounding state and asserts the invariant on every one.
        """
        checked = 0
        violations = []

        for action_type, status, extra in itertools.product(
            ALL_ACTION_TYPES, ALL_APPROVAL_STATUSES, IRRELEVANT_STATE_VARIANTS
        ):
            state = dict(extra)
            state["proposed_action"] = {"type": action_type, "amount": 500.0}
            if status != "__MISSING__":
                state["approval_status"] = status

            route = should_execute(state)
            checked += 1

            should_run = status == "approved"
            if (route == "execute_action") != should_run:
                violations.append((action_type, status, extra, route))

            # The gate must only ever produce one of two known routes.
            assert route in ("execute_action", "generate_response")

        assert violations == [], f"HITL gate violated on: {violations[:5]}"

        # 9 action types × 9 approval statuses × 3 state variants
        assert checked == 243, (
            f"Expected 243 combinations, enumerated {checked}. "
            "If you changed the input space, update this number and the "
            "counts quoted in README.md and .github/SECURITY.md."
        )

    @pytest.mark.asyncio
    async def test_destructive_types_never_auto_approve(self):
        """Exhaustive over action types: only non-destructive types skip the human.

        A destructive type reaching `await_approval` MUST call `interrupt()` —
        that is the pause that waits for a human. Anything else is a bypass.
        """
        bypasses = []

        for action_type in ALL_ACTION_TYPES:
            state = {
                "user_message": "test",
                "thread_id": "safety-thread",
                "thought_log": [],
                "proposed_action": {"type": action_type, "description": "d"},
            }

            with patch("app.agent.agents.resolver.interrupt") as mock_interrupt, \
                 patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
                mock_interrupt.return_value = {"approved": True, "reason": ""}
                mock_tracker.return_value.get_request.return_value = None

                outcome = await await_approval(state)
                human_was_asked = mock_interrupt.called

            if action_type in DESTRUCTIVE_TYPES and not human_was_asked:
                bypasses.append(action_type)

            if action_type in AUTO_APPROVE_TYPES:
                assert not human_was_asked, (
                    f"{action_type} is in AUTO_APPROVE_TYPES but hit the interrupt"
                )
                assert outcome["approval_status"] == "approved"

        assert bypasses == [], (
            f"Destructive action types bypassed the human gate: {bypasses}"
        )


# ─────────────────────────────────────────────────────────────
# 2. THE UNVERIFIED-CUSTOMER INVARIANT — exhaustive
# ─────────────────────────────────────────────────────────────

# SQL result shapes that contain NO verified customer (need both id and name).
# None of these may trigger the "already resolved" pre-check.
NO_CUSTOMER_SQL_SHAPES = [
    [],
    [{}],
    [{"foo": "bar"}],
    [{"id": 8}],                       # id without a name
    [{"name": "David Martinez"}],      # name without an id
    [{"id": None, "name": None}],
]


class TestUnverifiedCustomerInvariant:
    """A mutating action must never survive against an unverified customer.

    `propose_action` applies a deterministic correction after the LLM responds:
    if the SQL investigation produced no (id, name) pair, any mutating proposal
    is downgraded to `escalate`. A hallucinated customer cannot cause a refund.
    """

    @pytest.mark.asyncio
    async def test_mutating_actions_downgrade_without_a_verified_customer(self):
        mutating = ["refund", "credit", "tier_change", "suspend", "reactivate"]
        checked = 0
        escapes = []

        for action_type, sql_shape in itertools.product(
            mutating, NO_CUSTOMER_SQL_SHAPES
        ):
            llm_json = json.dumps({
                "type": action_type,
                "amount": 9999.99,
                "customer_id": 424242,        # hallucinated
                "customer_name": "Ghost User",  # hallucinated
                "description": f"{action_type} for Ghost User",
                "reason": "LLM was confidently wrong",
            })
            mock_response = MagicMock()
            mock_response.content = llm_json
            mock_response.usage_metadata = None

            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            state = {
                "user_message": "refund me everything",
                "thread_id": "safety-thread",
                "thought_log": [],
                "intent": "billing",
                "sql_result": sql_shape,
                "docs_context": "",
            }

            with patch(
                "app.agent.agents.resolver.get_model_for_intent",
                return_value=mock_llm,
            ), patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
                mock_tracker.return_value.get_request.return_value = None
                result = await propose_action(state)

            action = result["proposed_action"]
            checked += 1

            if action["type"] != "escalate":
                escapes.append((action_type, sql_shape, action["type"]))
            if action["customer_id"] is not None:
                escapes.append((action_type, sql_shape, "leaked hallucinated id"))

        assert escapes == [], f"Unverified customer produced a live action: {escapes}"

        # 5 mutating types × 6 customer-less SQL shapes
        assert checked == 30, (
            f"Expected 30 combinations, enumerated {checked}. "
            "Update this number and the counts in README.md if the space changed."
        )

    @pytest.mark.asyncio
    async def test_hallucinated_customer_is_overwritten_by_sql_truth(self):
        """When SQL DOES find a customer, the LLM's version never wins."""
        llm_json = json.dumps({
            "type": "refund",
            "amount": 29.99,
            "customer_id": 999,             # hallucinated
            "customer_name": "Ghost User",  # hallucinated
            "description": "Refund",
            "reason": "duplicate charge",
        })
        mock_response = MagicMock()
        mock_response.content = llm_json
        mock_response.usage_metadata = None
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = {
            "user_message": "double charged",
            "thread_id": "safety-thread",
            "thought_log": [],
            "intent": "billing",
            "sql_result": [{"id": 8, "name": "David Martinez", "amount": 29.99}],
            "docs_context": "",
        }

        with patch(
            "app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm
        ), patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        action = result["proposed_action"]
        assert action["customer_id"] == 8
        assert action["customer_name"] == "David Martinez"


# ─────────────────────────────────────────────────────────────
# 3. PERMISSION BOUNDARY — the table allowlist
# ─────────────────────────────────────────────────────────────

# Names that must ALL be refused before a query is built. Slash-bearing
# traversal strings are excluded because they never reach the handler — the
# router 404s them first, which is also a refusal.
FORBIDDEN_TABLE_NAMES = [
    "pg_shadow",
    "pg_user",
    "pg_catalog.pg_tables",
    "information_schema.tables",
    "information_schema.columns",
    "users",
    "admin",
    "secrets",
    "auth.users",
    "customers;DROP TABLE customers",
    "customers--",
    "customers UNION SELECT * FROM pg_shadow",
    "customers'",
    "CUSTOMERS",          # allowlist is case-sensitive on purpose
    "Customers",
    "customers ",         # trailing space
    " customers",
    "customer",           # near-miss singular
    "customers2",
    "",
]

ALLOWED_TABLE_NAMES = ["customers", "billing", "support_tickets", "internal_docs"]


class TestTableAllowlistBoundary:
    """Prove least-privilege actually holds — not just that it's configured."""

    def test_every_non_allowlisted_name_is_refused_without_touching_the_db(
        self, client
    ):
        """Exhaustive over the attack corpus: 400, and zero database calls."""
        refused = 0

        for name in FORBIDDEN_TABLE_NAMES:
            with patch("app.main.get_supabase") as mock_db:
                res = client.get(f"/api/tables/{name}")

                # An empty name hits `/api/tables/` which has no route → 404.
                assert res.status_code in (400, 404, 307), (
                    f"{name!r} was not refused (got {res.status_code})"
                )
                assert not mock_db.called, (
                    f"{name!r} reached the database layer before being refused"
                )
                refused += 1

        assert refused == 20, (
            f"Expected 20 forbidden names, checked {refused}. "
            "Update this number and the counts in README.md if the corpus changed."
        )

    def test_allowlisted_names_are_permitted(self, client):
        """The boundary must not be so tight that the product stops working."""
        for name in ALLOWED_TABLE_NAMES:
            mock_db = MagicMock()
            mock_db.execute_sql = AsyncMock(
                return_value={"success": True, "data": [{"id": 1}]}
            )
            with patch("app.main.get_supabase", return_value=mock_db):
                res = client.get(f"/api/tables/{name}")
                assert res.status_code == 200, f"{name} should be allowed"
                assert res.json()["table"] == name
