"""Knowledge Agent — Documentation Search.

The Knowledge Agent searches internal documentation for relevant policies,
procedures, and guidelines that inform the Resolution Agent's decision-making.

It bridges the gap between raw investigation data and actionable knowledge.
"""

from langsmith import traceable

from app.agent.state import AgentState
from app.db.supabase import get_supabase


AGENT_NAME = "Knowledge"
AGENT_DESCRIPTION = (
    "Searches internal documentation for relevant policies, procedures, "
    "and guidelines to support action proposals."
)


@traceable(name="search_docs")
async def search_docs(state: AgentState, config: dict | None = None) -> dict:
    """Search internal documentation for relevant policies/procedures."""
    db = get_supabase()
    
    # Extract keywords from intent and message
    search_terms = state.get("intent", "general")
    docs = await db.search_docs(search_terms)
    
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
                f"✓ [{AGENT_NAME}] Found {len(docs)} relevant internal documents"
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
