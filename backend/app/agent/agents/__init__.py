"""Aegis Multi-Agent Module.

This package organizes the Aegis workflow into 4 specialized agents:

- **Triage Agent** (classifier.py): Intent classification
- **Investigator Agent** (investigator.py): Customer validation + SQL investigation
- **Knowledge Agent** (researcher.py): Documentation search
- **Resolution Agent** (resolver.py): Action proposal, approval, execution, response
"""

from app.agent.agents.classifier import (  # noqa: F401
    classify_intent,
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
)
from app.agent.agents.researcher import (  # noqa: F401
    search_docs,
)
from app.agent.agents.resolver import (  # noqa: F401
    propose_action,
    await_approval,
    should_execute,
    execute_action,
    generate_response,
)

