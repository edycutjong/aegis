"""Drive Aegis from another agent over A2A.

    python examples/a2a_client.py                                  # live demo, sample ticket
    python examples/a2a_client.py --url http://localhost:8000 "Customer #10 ..."
    python examples/a2a_client.py --decision deny                  # no prompt

Discovers the Agent Card, streams the investigation, and when Aegis stops at
the approval gate, asks *you* (the human) before relaying a typed decision.
"""

import argparse
import asyncio

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers.proto_helpers import new_data_message, new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState
from google.protobuf.json_format import MessageToDict

LIVE = "https://api.aegis.edycu.dev"
SAMPLE = (
    "Customer #10 Chris Johnson was billed for his Pro subscription three times this month, "
    "one of them is marked duplicate. He wants the extra charge refunded."
)


async def stream(client, message) -> tuple[str, str, int, dict]:
    """Send a message, print progress, return (task_id, context_id, final_state, artifacts)."""
    task_id = context_id = ""
    state = TaskState.TASK_STATE_UNSPECIFIED
    artifacts: dict = {}
    async for event in client.send_message(SendMessageRequest(message=message)):
        if event.HasField("task"):
            task_id, context_id = event.task.id, event.task.context_id
            state = event.task.status.state
        elif event.HasField("status_update"):
            state = event.status_update.status.state
            for part in event.status_update.status.message.parts:
                if part.text:
                    print(f"  {TaskState.Name(state).removeprefix('TASK_STATE_').lower():>14} │ {part.text}")
        elif event.HasField("artifact_update"):
            artifact = MessageToDict(event.artifact_update.artifact)
            artifacts[artifact.get("name")] = artifact["parts"][0]
    return task_id, context_id, state, artifacts


async def main(url: str, ticket: str, decision: str | None, token: str | None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=120, headers=headers) as http:
        card = await A2ACardResolver(http, url).get_agent_card()
        print(f"→ {card.name} {card.version} · skills: {', '.join(s.id for s in card.skills)}")
        client = await create_client(card, ClientConfig(httpx_client=http, streaming=True))
        print(f"→ ticket: {ticket}\n")

        task_id, context_id, state, artifacts = await stream(client, new_text_message(ticket, role=Role.ROLE_USER))

        if state == TaskState.TASK_STATE_INPUT_REQUIRED:
            action = artifacts.get("proposed-action", {}).get("data", {})
            print(f"\n⏸  Aegis wants to run: {action.get('type')} — {action.get('description')}")
            choice = decision or input("   approve / deny? ").strip().lower()
            if choice not in ("approve", "deny"):
                print("   No decision sent. The task stays paused; nothing executed.")
                return
            reply = new_data_message(
                {"decision": choice, "reason": "relayed from a human via the A2A demo client"},
                role=Role.ROLE_USER, task_id=task_id, context_id=context_id,
            )
            print()
            _, _, state, artifacts = await stream(client, reply)

        print(f"\n■ {TaskState.Name(state).removeprefix('TASK_STATE_').lower()}")
        receipt = artifacts.get("receipt", {}).get("data")
        if receipt:
            print(f"  cost ${receipt.get('total_cost_usd', 0):.4f} · {receipt.get('duration_seconds')}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ticket", nargs="?", default=SAMPLE)
    parser.add_argument("--url", default=LIVE, help=f"Aegis base URL (default {LIVE})")
    parser.add_argument("--decision", choices=["approve", "deny"], help="skip the prompt")
    parser.add_argument("--token", help="approver bearer token, if the server requires one")
    args = parser.parse_args()
    asyncio.run(main(args.url, args.ticket, args.decision, args.token))
