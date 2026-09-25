"""The Aegis Agent Card, served at /.well-known/agent-card.json.

The card is what another agent reads to decide whether and how to call Aegis:
one skill, one JSON-RPC interface, and the shape of the approval decision.
"""

from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    HTTPAuthSecurityScheme,
    SecurityScheme,
)
from a2a.utils.constants import PROTOCOL_VERSION_0_3, PROTOCOL_VERSION_CURRENT

RPC_PATH = "/a2a"
REPO_URL = "https://github.com/edycutjong/aegis"

SKILL_DESCRIPTION = (
    "Investigates a Tier-2 support ticket against the live customer database and internal "
    "policy, then proposes exactly one action: refund, credit, tier_change, suspend, "
    "reactivate, escalate or resolve. `resolve` completes on its own. Every other action "
    "stops the task in `input-required` with a `proposed-action` artifact, and nothing "
    "executes until the caller sends a structured decision: a data part "
    '{"decision": "approve" | "deny", "reason": "..."} on the same task. '
    "Free-text replies are never interpreted as a decision."
)


def build_agent_card(public_url: str, version: str, approver_token_required: bool) -> AgentCard:
    rpc_url = f"{public_url.rstrip('/')}{RPC_PATH}"
    card = AgentCard(
        name="Aegis",
        description=(
            "A multi-agent support engine that investigates tickets against a live database, "
            "proposes one action, and stops for a human before anything that moves money or "
            "changes an account."
        ),
        version=version,
        provider=AgentProvider(organization="Aegis", url=REPO_URL),
        documentation_url=f"{REPO_URL}/blob/main/docs/a2a.md",
        # One endpoint speaks both: v1.0, and v0.3 for the many agents still on it.
        supported_interfaces=[
            AgentInterface(url=rpc_url, protocol_binding="JSONRPC", protocol_version=version_)
            for version_ in (PROTOCOL_VERSION_CURRENT, PROTOCOL_VERSION_0_3)
        ],
        # Push notifications stay off: a caller-supplied webhook URL is an SSRF
        # primitive, and streaming plus GetTask already cover progress.
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        skills=[
            AgentSkill(
                id="resolve-support-ticket",
                name="Resolve a support ticket",
                description=SKILL_DESCRIPTION,
                tags=["customer-support", "human-in-the-loop", "billing", "sql"],
                examples=[
                    "Customer #10 Chris Johnson was billed for his Pro subscription three times this month. "
                    "He wants the extra charge refunded.",
                    "Customer #2 James Wilson needs a copy of last month's invoice for tax purposes.",
                ],
                input_modes=["text/plain", "application/json"],
                output_modes=["text/plain", "application/json"],
            )
        ],
    )
    if approver_token_required:
        card.security_schemes["approverBearer"].CopyFrom(SecurityScheme(
            http_auth_security_scheme=HTTPAuthSecurityScheme(
                scheme="bearer",
                description=(
                    "Needed only to approve or deny a proposed action. Submitting tickets "
                    "and reading tasks do not require it."
                ),
            )
        ))
    return card
