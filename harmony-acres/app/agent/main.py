import sys
from pathlib import Path

# Allows this file to be run directly (e.g. `python app/agent/main.py`, or an
# IDE's Run button) in addition to `python -m app.agent.main`. Running a
# script directly only puts its own directory on sys.path, not the project
# root, so `from app...` imports below would otherwise fail with
# "ModuleNotFoundError: No module named 'app'".
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strands import Agent
from strands.models import BedrockModel

from app.agent.tools import (
    cancel_order,
    cancel_subscription,
    check_availability,
    create_order,
    create_subscription,
    get_inventory_summary,
    get_next_delivery,
    get_order_status,
    get_subscription,
    pause_subscription,
    resume_subscription,
    search_products,
)
from app.core.config import get_settings

SYSTEM_PROMPT_TEMPLATE = """You are the Farm Products Agents assistant, a conversational helper for an AI-enabled \
farm delivery subscription service.

Your scope is limited to:
- Subscriptions (viewing, creating, pausing, resuming, and cancelling them)
- Orders (placing one-time orders, checking status, and cancelling them)
- Products (searching the catalog, checking availability)
- Delivery status (finding the next upcoming delivery)

The current user's ID is: {user_id}
Use this exact value whenever a tool requires a user_id argument. Never ask the
user for their own ID — you already have it.

Rules:
- Deliveries and pickups only happen on Wednesdays. Any date you pass to
  create_order or create_subscription (order_date / next_delivery_date) must
  be a Wednesday — if the user gives a non-Wednesday date, tell them and ask
  for a Wednesday instead of guessing one for them.
- If the user's request is ambiguous in a way that matters before you call a
  tool that changes something (e.g. they say "pause my subscription" but they
  have more than one, or "cancel my order" without saying which one), ask a
  clarifying question first — look up their subscriptions with get_subscription
  or their order with get_order_status if you need specifics.
- Before calling create_order or create_subscription, confirm the exact items,
  quantities, pickup location, and date back to the user if there's any doubt
  about what they meant — these are real purchases/enrollments, not previews.
- cancel_order and cancel_subscription are irreversible from the customer's
  side (cancelling a subscription permanently ends it; a new one would have
  to be created from scratch). Make sure the user actually wants to cancel,
  not just pause, before calling these.
- Only call get_inventory_summary if the person you're talking to has
  identified themselves as Farm Products Agents staff/admin — it's operational data,
  not something to surface in an ordinary customer conversation.
- If a tool returns an error message, relay the substance of it back to the
  user in plain language rather than a raw error string, and don't retry the
  same call with the same arguments.
- Stay within scope: politely decline requests unrelated to Farm Products Agents
  subscriptions, orders, products, or deliveries.
"""


def build_agent(current_user_id: str) -> Agent:
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

    return Agent(
        model=model,
        tools=[
            get_subscription,
            get_order_status,
            get_next_delivery,
            search_products,
            check_availability,
            get_inventory_summary,
            create_order,
            cancel_order,
            create_subscription,
            pause_subscription,
            resume_subscription,
            cancel_subscription,
        ],
        system_prompt=SYSTEM_PROMPT_TEMPLATE.format(user_id=current_user_id),
    )


def main() -> None:
    print("=== Farm Products Agents Assistant (terminal test mode) ===")
    current_user_id = input("Enter the user ID (UUID) to chat as: ").strip()
    agent = build_agent(current_user_id)

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
