"""LangGraph workflow definition for the Aegis agent.

This is the brain of the system — a stateful graph that orchestrates
the multi-agent support workflow with HITL interrupts.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import AgentState
from app.agent.nodes import (
    classify_intent,
    validate_customer,
    should_proceed_after_validation,
    write_sql,
    execute_sql,
    should_retry_sql,
    search_docs,
    propose_action,
    await_approval,
    should_execute,
    execute_action,
    generate_response,
)


def build_agent_graph():
    """Build and compile the Aegis agent graph.
    
    The workflow:
    1. classify_intent       → Determine ticket category (fast model)
    2. validate_customer     → Check customer exists in DB
       ↳ not found          → generate_response → END (short-circuit)
    3. write_sql             → Generate investigation query (smart model)
    4. execute_sql           → Run query on Supabase
       ↳ on error           → write_sql (self-healing loop, max 3 retries)
    5. search_docs           → Find relevant internal documentation
    6. propose_action        → Synthesize findings into action (smart model)
    7. await_approval        → HITL interrupt — pause for human decision
       ↳ approved            → execute_action → generate_response → END
       ↳ denied              → generate_response → END
    """
    
    builder = StateGraph(AgentState)
    
    # Add all nodes
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("validate_customer", validate_customer)
    builder.add_node("write_sql", write_sql)
    builder.add_node("execute_sql", execute_sql)
    builder.add_node("search_docs", search_docs)
    builder.add_node("propose_action", propose_action)
    builder.add_node("await_approval", await_approval)
    builder.add_node("execute_action", execute_action)
    builder.add_node("generate_response", generate_response)
    
    # Define edges
    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "validate_customer")
    
    # Customer validation gate
    builder.add_conditional_edges(
        "validate_customer",
        should_proceed_after_validation,
        {
            "write_sql": "write_sql",               # Customer found → investigate
            "generate_response": "generate_response", # Not found → short-circuit
        },
    )
    builder.add_edge("write_sql", "execute_sql")
    
    # Self-healing SQL loop + zero-results guard
    builder.add_conditional_edges(
        "execute_sql",
        should_retry_sql,
        {
            "write_sql": "write_sql",               # Retry on error
            "search_docs": "search_docs",            # Has data → continue
            "generate_response": "generate_response", # 0 records → short-circuit
        },
    )
    
    builder.add_edge("search_docs", "propose_action")
    builder.add_edge("propose_action", "await_approval")
    
    # HITL decision routing
    builder.add_conditional_edges(
        "await_approval",
        should_execute,
        {
            "execute_action": "execute_action",       # Approved
            "generate_response": "generate_response",  # Denied
        },
    )
    
    builder.add_edge("execute_action", "generate_response")
    builder.add_edge("generate_response", END)
    
    # Compile with checkpointer for HITL state persistence
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    
    return graph


# Module-level graph instance
agent_graph = build_agent_graph()
