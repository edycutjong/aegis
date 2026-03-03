"""LangGraph agent state definition for Aegis."""

from typing import Literal, TypedDict


class ActionProposal(TypedDict, total=False):
    """A proposed action for human approval."""
    type: str          # refund, tier_change, credit, escalate, resolve
    amount: float      # monetary amount if applicable
    customer_id: int
    customer_name: str
    description: str   # human-readable description
    reason: str        # why the agent proposes this


class TokenUsage(TypedDict, total=False):
    """Token usage tracking per step."""
    prompt_tokens: int
    completion_tokens: int
    model: str
    cost_usd: float


class AgentState(TypedDict, total=False):
    """Full state for the Aegis agent workflow.
    
    This state flows through all LangGraph nodes and persists
    across interrupt/resume cycles via the checkpointer.
    """
    # Input  
    user_message: str
    thread_id: str
    
    # Intent classification  
    intent: Literal["billing", "technical", "account", "general"]
    intent_confidence: float
    
    # SQL investigation
    sql_query: str
    sql_result: list[dict]
    sql_error: str
    sql_retry_count: int
    customer_found: bool
    customer_candidates: list[dict]
    
    # Documentation search
    docs_context: str
    relevant_docs: list[str]
    
    # Action proposal (HITL)
    proposed_action: ActionProposal
    approval_status: Literal["pending", "approved", "denied", "not_required"]
    denial_reason: str
    
    # Execution
    execution_result: str
    
    # Multi-agent tracking
    active_agent: str  # Which agent is currently working (Triage, Investigator, Knowledge, Resolution)
    
    # Observability
    thought_log: list[str]
    token_usage: list[TokenUsage]
    total_cost_usd: float
    models_used: list[str]
    cache_hit: bool
    
    # Error handling
    error: str
    
    # Final response
    final_response: str
