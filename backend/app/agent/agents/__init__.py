"""Aegis Multi-Agent Module.

This package organizes the Aegis workflow into 4 specialized agents:

- **Triage Agent** (classifier.py): Intent classification
- **Investigator Agent** (investigator.py): Customer validation + SQL investigation
- **Knowledge Agent** (researcher.py): Documentation search
- **Resolution Agent** (resolver.py): Action proposal, approval, execution, response
"""

from app.agent.agents.classifier import (  # noqa: F401
    classify_intent,
    AGENT_NAME as TRIAGE_AGENT_NAME,
    AGENT_DESCRIPTION as TRIAGE_AGENT_DESCRIPTION,
)
from app.agent.agents.investigator import (  # noqa: F401
    validate_customer,
    should_proceed_after_validation,
    write_sql,
    execute_sql,
    should_retry_sql,
    _extract_customer_info,
    _fuzzy_name_match,
    _search_customers_by_name,
    _status_warning,
    AGENT_NAME as INVESTIGATOR_AGENT_NAME,
    AGENT_DESCRIPTION as INVESTIGATOR_AGENT_DESCRIPTION,
)
from app.agent.agents.researcher import (  # noqa: F401
    search_docs,
    AGENT_NAME as KNOWLEDGE_AGENT_NAME,
    AGENT_DESCRIPTION as KNOWLEDGE_AGENT_DESCRIPTION,
)
from app.agent.agents.resolver import (  # noqa: F401
    propose_action,
    await_approval,
    should_execute,
    execute_action,
    generate_response,
    AGENT_NAME as RESOLUTION_AGENT_NAME,
    AGENT_DESCRIPTION as RESOLUTION_AGENT_DESCRIPTION,
)


# Agent registry for programmatic access
AGENTS = {
    "Triage": {
        "name": TRIAGE_AGENT_NAME,
        "description": TRIAGE_AGENT_DESCRIPTION,
        "nodes": ["classify_intent"],
    },
    "Investigator": {
        "name": INVESTIGATOR_AGENT_NAME,
        "description": INVESTIGATOR_AGENT_DESCRIPTION,
        "nodes": ["validate_customer", "write_sql", "execute_sql"],
    },
    "Knowledge": {
        "name": KNOWLEDGE_AGENT_NAME,
        "description": KNOWLEDGE_AGENT_DESCRIPTION,
        "nodes": ["search_docs"],
    },
    "Resolution": {
        "name": RESOLUTION_AGENT_NAME,
        "description": RESOLUTION_AGENT_DESCRIPTION,
        "nodes": ["propose_action", "await_approval", "execute_action", "generate_response"],
    },
}
