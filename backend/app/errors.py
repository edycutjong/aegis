"""User-safe error text, shared by the web API and the A2A server."""


def public_error(error: Exception) -> str:
    """User-safe error text. Raw provider errors carry account/org ids."""
    text = f"{type(error).__name__} {error}"
    if "429" in text or "RateLimit" in text or "ResourceExhausted" in text or "quota" in text.lower():
        return "The model providers are rate-limiting this demo right now. Please try again in a minute."
    if "Timeout" in text or "timed out" in text.lower():
        return "A model provider timed out. Please try again."
    return f"The agent workflow failed ({type(error).__name__})."
