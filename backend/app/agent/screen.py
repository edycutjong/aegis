"""Input screening — the first layer of prompt-injection defense.

Two independent detectors, because neither is enough alone:

- **Llama Prompt Guard 2** (via Groq) — a classifier trained on jailbreaks. It
  scores "IGNORE ALL PREVIOUS INSTRUCTIONS" at 0.998, but data-exfiltration
  requests, fake `<system>` tags, authority claims, and JSON smuggling all score
  below 0.01 (measured against evals/golden.jsonl). It is a jailbreak detector,
  not an intent detector.
- **Deterministic rules** — narrow patterns for exactly those gaps. Each rule
  is tested for false positives against every benign golden ticket.

A flagged ticket is not rejected: it still gets investigated, but the
Resolution agent must escalate it to a human (enforced in code, not prompt).
Screening fails open — if Prompt Guard is unreachable the rules still run, and
the approval gate and SQL guard still stand behind them.
"""

import re

import httpx

from app.config import get_settings

PROMPT_GUARD_MODEL = "meta-llama/llama-prompt-guard-2-86m"
PROMPT_GUARD_THRESHOLD = 0.5
PROMPT_GUARD_TIMEOUT_S = 3.0

RULES: dict[str, re.Pattern] = {
    "instruction-override": re.compile(
        r"\b(ignore|disregard|forget)\b.{0,20}\b(previous|prior|above|all|your)\b.{0,20}\b(instructions?|rules?|prompts?)\b"
        r"|\byou are now\b|\b(admin|developer|god|jailbreak) mode\b|\bsystem prompt\b",
        re.IGNORECASE,
    ),
    "role-spoofing": re.compile(r"</?\s*(system|assistant|user|developer)\s*>|\[(system|assistant)\]", re.IGNORECASE),
    "approval-bypass": re.compile(
        r"\b(without|no|skip|bypass)\s+(human\s+|manager\s+)?(review|approval)\b|\bno approval needed\b"
        r"|\bpre-?approved\b|\bemergency override\b|\bskips? approval\b"
        r"|\bi\s*(am|'m)\s+the\s+(ceo|cto|cfo|owner|admin|administrator)\b",
        re.IGNORECASE,
    ),
    "data-exfiltration": re.compile(
        r"\binformation_schema\b|\bpg_catalog\b|\bpg_(user|shadow|roles|authid|tables)\b|\bauth\.users\b"
        r"|\b(write|run|execute|give me|show me)\b.{0,25}\b(sql|queries|query)\b"
        r"|\b(every|all)\s+(row|rows|table|tables)\b"
        r"|\bjoin\b.{0,30}\b[a-z_]+\.[a-z_]+\b.{0,20}\btables?\b"
        r"|\b(paste|dump|full text of)\b.{0,40}\b(documents?|docs|procedures?)\b",
        re.IGNORECASE,
    ),
    "hidden-text": re.compile("[‪-‮⁦-⁩​-‏]"),
    "action-smuggling": re.compile(
        r'"type"\s*:\s*"(refund|credit|tier_change|suspend|reactivate|resolve)"'
        r"|\b(respond|reply|output)\b.{0,30}\baction type\b",
        re.IGNORECASE,
    ),
}


def rule_flags(message: str) -> list[str]:
    """Names of every deterministic rule the message trips."""
    return [name for name, pattern in RULES.items() if pattern.search(message)]


async def prompt_guard_score(message: str) -> float | None:
    """Jailbreak probability from Llama Prompt Guard 2, or None if unavailable."""
    key = get_settings().groq_api_key
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=PROMPT_GUARD_TIMEOUT_S) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": PROMPT_GUARD_MODEL, "messages": [{"role": "user", "content": message}]},
            )
        if response.status_code != 200:
            return None
        return float(response.json()["choices"][0]["message"]["content"].strip())
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return None


async def screen(message: str) -> tuple[list[str], float | None]:
    """Run both detectors. Returns (flags, prompt_guard_score)."""
    flags = rule_flags(message)
    score = await prompt_guard_score(message)
    if score is not None and score >= PROMPT_GUARD_THRESHOLD:
        flags = ["jailbreak (prompt-guard)", *flags]
    return flags, score
