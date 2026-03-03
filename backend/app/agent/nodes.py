"""LangGraph agent nodes for the Aegis workflow.

⚠ BACKWARD-COMPATIBILITY SHIM ⚠
This module re-exports all node functions from the new multi-agent package
(app.agent.agents.*) so existing imports continue to work unchanged.

The actual implementations now live in:
  - agents/classifier.py     → Triage Agent (classify_intent)
  - agents/investigator.py   → Investigator Agent (validate_customer, write_sql, execute_sql)
  - agents/researcher.py     → Knowledge Agent (search_docs)
  - agents/resolver.py       → Resolution Agent (propose_action, await_approval, execute_action, generate_response)
"""

from app.agent.agents.classifier import classify_intent  # noqa: F401
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
)
from app.agent.agents.researcher import search_docs  # noqa: F401
from app.agent.agents.resolver import (  # noqa: F401
    propose_action,
    await_approval,
    should_execute,
    execute_action,
    generate_response,
)
