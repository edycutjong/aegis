"""Knowledge Agent — Documentation Search.

The Knowledge Agent searches internal documentation for relevant policies,
procedures, and guidelines that inform the Resolution Agent's decision-making.
It bridges the gap between raw investigation data and actionable knowledge.

Retrieval is lexical ranking over the whole knowledge base: each document is
scored by how many of the ticket's terms it contains (title hits weigh more),
with a small boost when its category matches the classified intent. The
previous version searched for the intent word alone ("billing"), so a ticket
about an outage never saw the outage-compensation policy and the agent
invented a $5 credit where policy says 50% of the monthly bill. Caught by the
`core-outage-credit-4` eval.
"""

import re

from langsmith import traceable

from app.agent.state import AgentState
from app.db.supabase import get_supabase


AGENT_NAME = "Knowledge"
AGENT_DESCRIPTION = (
    "Searches internal documentation for relevant policies, procedures, "
    "and guidelines to support action proposals."
)

TOP_K = 4
_STOPWORDS = frozenset(
    "the and for with that this from have has his her their they them was were are "
    "you your our not but can will would could should about into what when which who "
    "why how please customer says said wants want asks need needs account plan "
    # Ticket boilerplate that matches policy titles by accident
    # ("process a refund" → "Account Deletion Process").
    "process processed investigate confirm confirmed issue help month week today".split()
)


def _terms(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9]+", text.lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


def _stem(term: str) -> str:
    """Crude suffix strip so 'outage'/'outages', 'charged'/'charges' meet."""
    for suffix in ("ing", "ed", "s"):
        if term.endswith(suffix) and len(term) - len(suffix) >= 4:
            term = term[: -len(suffix)]
            break
    return term[:-1] if term.endswith("e") and len(term) > 4 else term


def rank_docs(docs: list[dict], ticket: str, intent: str | None, k: int = TOP_K) -> list[dict]:
    """Return the k most relevant docs; zero-score docs are never returned."""
    query = {_stem(t) for t in _terms(ticket)}
    scored = []
    for doc in docs:
        title = {_stem(t) for t in _terms(doc.get("title", ""))}
        body = {_stem(t) for t in _terms(doc.get("content", ""))}
        score = 3 * len(query & title) + len(query & body)
        if score and intent and doc.get("category") == intent:
            score += 2
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:k]]


@traceable(name="search_docs")
async def search_docs(state: AgentState, config: dict | None = None) -> dict:
    """Search internal documentation for relevant policies/procedures."""
    db = get_supabase()
    docs = rank_docs(await db.list_docs(), state["user_message"], state.get("intent"))

    if docs:
        docs_text = "\n\n".join(
            f"[{d['title']}] ({d['category']})\n{d['content'][:500]}"
            for d in docs
        )
        return {
            "docs_context": docs_text,
            "relevant_docs": [d["title"] for d in docs],
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"✓ [{AGENT_NAME}] Found {len(docs)} relevant internal documents: "
                + ", ".join(d["title"] for d in docs)
            ],
        }

    return {
        "docs_context": "No internal documentation found for this topic.",
        "relevant_docs": [],
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"✓ [{AGENT_NAME}] No specific internal docs found — using general knowledge"
        ],
    }
