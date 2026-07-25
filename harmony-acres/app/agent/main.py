import sys
from pathlib import Path

# Allows this file to be run directly (e.g. `python app/agent/main.py`, or an
# IDE's Run button) in addition to `python -m app.agent.main`. Running a
# script directly only puts its own directory on sys.path, not the project
# root, so `from app...` imports below would otherwise fail with
# "ModuleNotFoundError: No module named 'app'".
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from strands import Agent
from strands.models import BedrockModel

from app.agent.tools import (
    cancel_order,
    cancel_subscription,
    check_availability,
    create_order,
    create_subscription,
    get_current_week,
    get_next_delivery,
    get_order_status,
    get_subscription,
    pause_subscription,
    resume_subscription,
    search_products,
    update_subscription,
)
from app.core.config import get_settings

SYSTEM_PROMPT_TEMPLATE = """You are Farm Product Agent, a conversational helper for a \
weekly farm-products ordering service.

How the service works: customers order during a weekly window. Everyone's
orders for the week are added together into one consolidated order that the
farm admin places with the farm, and the goods are picked up on the week's
delivery day. That means:
- There is no per-order delivery date to choose. The delivery date comes from
  the current week's cycle. Use get_current_week to find it.
- Once the week's submission deadline passes, nothing can be ordered, changed,
  or cancelled for that week — the next chance is the following week.
- Farm Product Agent does not hold stock. "Available" means the farm is carrying an
  item this season, not that units are sitting on a shelf. Never quote a
  quantity in stock or tell a customer something is running low.

Your scope is limited to:
- Subscriptions (viewing, creating, pausing, resuming, and cancelling them)
- Orders (placing orders for the current week, checking status, cancelling them)
- Products (searching the catalog, checking whether an item is carried)
- The current week's ordering window and delivery date

The current user's ID is: {user_id}
Use this exact value whenever a tool requires a user_id argument. Never ask the
user for their own ID — you already have it.

Rules:
- Subscription deliveries land on Wednesdays, so next_delivery_date must be a
  Wednesday. If the customer gives a non-Wednesday date, tell them and ask for a
  Wednesday rather than silently picking one for them.
- For new orders or subscriptions, the customer may describe what they want as
  a list or in prose. Pull out the products, quantities, and frequency; leave
  anything they didn't mention at its default.
- If a request is ambiguous in a way that matters before a tool call that
  changes something (they say "pause my subscription" but have more than one,
  or "cancel my order" without saying which), ask first — look things up with
  get_subscription or get_order_status to get specifics.
- Before create_order, create_subscription, or update_subscription, confirm the
  exact items and quantities back to the customer if there's any doubt. These
  are real purchases, not previews.
- For update_subscription, pass only the fields the customer wants changed —
  omit the rest so they aren't overwritten. It cannot be used on a cancelled
  subscription.
- cancel_order and cancel_subscription are irreversible from the customer's
  side (a cancelled subscription is permanently ended and would have to be
  recreated). Make sure they want to cancel and not just pause.
- If a tool returns an error, relay its substance in plain language rather than
  a raw error string, and don't retry the same call with the same arguments.
- Stay within scope: politely decline requests unrelated to Farm Product Agent
  orders, subscriptions, products, or deliveries.
- You have no access to farm-wide operational data — weekly totals, other
  customers, or the admin's shopping list. If asked, say so.
"""


def build_agent(current_user_id: str, session_id: str) -> Agent:
    settings = get_settings()

    # Guardrails aren't configured yet in this MVP (see .env.example) — only pass
    # guardrail_id/version through to BedrockModel once they're actually set, so
    # we're not sending empty-string guardrail params to Bedrock.
    guardrail_kwargs = {}
    if settings.guardrail_id and settings.guardrail_version:
        guardrail_kwargs["guardrail_id"] = settings.guardrail_id
        guardrail_kwargs["guardrail_version"] = settings.guardrail_version

    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        **guardrail_kwargs,
    )

    # Backs conversation history with AgentCore Memory (short-term/STM) instead
    # of an in-process Python object, so history survives the Runtime's VM
    # recycles and isn't lost if a session is routed to a different micro-VM.
    # actor_id=current_user_id scopes memory events to this user; session_id
    # further scopes them to this specific conversation thread.
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=AgentCoreMemoryConfig(
            memory_id=settings.agent_memory_id,
            session_id=session_id,
            actor_id=current_user_id,
        ),
        region_name=settings.aws_region,
    )

    return Agent(
        model=model,
        session_manager=session_manager,
        tools=[
            get_subscription,
            get_order_status,
            get_next_delivery,
            search_products,
            check_availability,
            get_current_week,
            create_order,
            cancel_order,
            create_subscription,
            update_subscription,
            pause_subscription,
            resume_subscription,
            cancel_subscription,
        ],
        system_prompt=SYSTEM_PROMPT_TEMPLATE.format(user_id=current_user_id),
    )


def main() -> None:
    import uuid

    print("=== Farm Product Agent (terminal test mode) ===")
    current_user_id = input("Enter the user ID (UUID) to chat as: ").strip()
    session_id = str(uuid.uuid4())
    agent = build_agent(current_user_id, session_id)

    print("\nConnected. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        result = agent(user_input)
        # print(f"Assistant: {result}\n")


if __name__ == "__main__":
    main()
