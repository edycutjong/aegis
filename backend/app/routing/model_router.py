"""Dynamic model routing for cost optimization.

Routes simple tasks to fast/cheap models and complex tasks to powerful/expensive ones.
This is Flex 2: Cost Engineering — proving you protect profit margins.
"""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from app.config import get_settings

# Model pricing per 1M tokens (input/output)
MODEL_PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro-preview-05-06": {"input": 1.25, "output": 10.00},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-20250514": {"input": 0.80, "output": 4.00},
}

# Task → Model complexity mapping
TASK_MODEL_MAP = {
    "classify_intent": "fast",      # Simple classification → cheap model
    "write_sql": "smart",           # Complex SQL generation → powerful model
    "search_docs": "fast",          # Document retrieval → cheap model
    "propose_action": "smart",      # Critical reasoning → powerful model
    "generate_response": "fast",    # Response formatting → cheap model
}


def get_model(task: str, override_model: str | None = None):
    """Get the appropriate LLM for a given task.
    
    Args:
        task: The agent task name (e.g., 'classify_intent', 'write_sql')
        override_model: Optional specific model to use
        
    Returns:
        A LangChain chat model instance
    """
    settings = get_settings()
    
    if override_model:
        model_name = override_model
    else:
        complexity = TASK_MODEL_MAP.get(task, "fast")
        model_name = settings.smart_model if complexity == "smart" else settings.fast_model
    
    return _create_model(model_name)


def _create_model(model_name: str):
    """Create a LangChain model instance by name."""
    settings = get_settings()
    
    if model_name.startswith("gemini"):
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )
    elif model_name.startswith("gpt") or model_name.startswith("o"):
        return ChatOpenAI(
            model=model_name,
            api_key=settings.openai_api_key,
            temperature=0.1,
        )
    elif model_name.startswith("claude"):
        return ChatAnthropic(
            model=model_name,
            api_key=settings.anthropic_api_key,
            temperature=0.1,
        )
    else:
        # Default to Gemini Flash as cheapest option
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )


def get_cost_per_token(model_name: str) -> dict:
    """Get pricing for a specific model."""
    return MODEL_PRICING.get(model_name, {"input": 0.0, "output": 0.0})


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate USD cost for a specific LLM call."""
    pricing = get_cost_per_token(model_name)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)
