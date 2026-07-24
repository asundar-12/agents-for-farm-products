"""The admin assistant.

Structurally a twin of app/agent/main.py's customer agent — same Bedrock model,
same AgentCore memory session manager. Only two things change, and they're the
two things that *should*: the system prompt and the toolset. Everything a
customer must never see is kept out by giving this agent a different set of
tools, not by asking the customer agent to behave.
"""

import sys
from pathlib import Path

# Same direct-run shim as main.py: `python app/agent/admin_main.py` only puts
# this file's own directory on sys.path, not the project root, so `from app...`
# would fail without this.
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from strands import Agent
from strands.models import BedrockModel

from app.agent.admin_tools import (
    get_non_submitters,
    get_shopping_list,
    get_week_summary,
    list_recent_weeks,
    save_week_summary,
)
from app.core.config import get_settings

SYSTEM_PROMPT = """You are the Farm Product Agent admin assistant, a helper for the farm \
operator who runs the weekly consolidated order.

How the service works: customers order during a weekly window. When it closes,
every order plus every subscription due that week is rolled up into one
consolidated order per product. You help the operator understand that rolled-up
demand and decide what to actually buy from the farm.

You are talking to farm staff, not a customer. It is appropriate to discuss
farm-wide totals, individual customers by name, costs, and who has or hasn't
ordered — this is the operator's own operational data.

What you can do:
- Report the week's headline numbers (get_week_summary).
- Break down the consolidated buy list, including who ordered what
  (get_shopping_list).
- Say who hasn't ordered yet, and who has an unsubmitted draft
  (get_non_submitters).
- Find past weeks and their status (list_recent_weeks).
- Write a summary of a week and, if asked, save it to the week's notes
  (save_week_summary).

Terminology:
- When referring to customers who have demand in a week, say they "placed an
  order" rather than "contributed" or "are contributing". A customer's demand
  can come from a one-off order they submitted or from a subscription due that
  week — both count as having placed an order for the week. Only distinguish the
  two ("via a subscription") when the operator is asking specifically about
  subscriptions versus one-off orders.

Rules:
- Most questions are about the current week. Only pass a cycle_id when the
  operator clearly means a past week — use list_recent_weeks to find it first.
- You cannot place, approve, or receive orders, and you cannot change customer
  orders or line quantities. Those are deliberate button-clicks in the
  dashboard, not chat actions. If asked to do one, explain that it has to be
  done from the dashboard and offer the numbers they'd need to decide.
- When numbers matter (costs, quantities), read them with a tool rather than
  estimating. Don't guess totals.
- Only call save_week_summary when the operator actually asks you to save or
  record a summary. Summarizing out loud doesn't require saving.
- If a tool returns an error, relay its substance in plain language rather than
  a raw error string, and don't retry the same call with the same arguments.
- Stay within scope: this is about the weekly order, its customers, products,
  and demand. Politely decline unrelated requests.
"""


def build_admin_agent(current_user_id: str, session_id: str) -> Agent:
    settings = get_settings()

    # Same guardrail handling as the customer agent: only forward the guardrail
    # params once they're actually configured, so we never send empty strings.
    guardrail_kwargs = {}
    if settings.guardrail_id and settings.guardrail_version:
        guardrail_kwargs["guardrail_id"] = settings.guardrail_id
        guardrail_kwargs["guardrail_version"] = settings.guardrail_version

    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        **guardrail_kwargs,
    )

    # actor_id is the admin's own user id, so their assistant history is scoped
    # to them and never bleeds into a customer's memory namespace — the two
    # agents share the same AgentCore Memory resource but not the same actors.
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
            get_week_summary,
            get_shopping_list,
            get_non_submitters,
            list_recent_weeks,
            save_week_summary,
        ],
        system_prompt=SYSTEM_PROMPT,
    )


def main() -> None:
    """Terminal harness for local testing, mirroring app/agent/main.py.

    Hits real Bedrock and AgentCore Memory but needs no deployment — the fast
    way to sanity-check the admin agent's prompt and tools before an
    `agentcore launch`. The user id here only scopes conversation memory; the
    admin tools are farm-wide and don't filter by it.
    """
    import uuid

    print("=== Farm Product Agent — ADMIN assistant (terminal test mode) ===")
    current_user_id = input("Enter an admin user ID (UUID) to chat as: ").strip()
    session_id = str(uuid.uuid4())
    agent = build_admin_agent(current_user_id, session_id)

    print("\nConnected. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        agent(user_input)


if __name__ == "__main__":
    main()
