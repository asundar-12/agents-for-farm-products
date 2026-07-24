import sys
from pathlib import Path

# Same fix as app/agent/main.py: running this file directly (`python
# app/agent/runtime.py`, or how AgentCore's container invokes it) only puts
# this file's own directory on sys.path, not the project root, so the
# `from app...` import below would otherwise fail with "No module named 'app'".
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from app.agent.admin_main import build_admin_agent
from app.agent.main import build_agent

# BedrockAgentCoreApp is a small HTTP server AgentCore knows how to run inside
# the deployed container. It exposes POST /invocations (calls our entrypoint
# below) and GET /ping (health check) — we don't write either route ourselves.
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict):
    """Called once per request to POST /invocations.

    `payload` is exactly the JSON body our FastAPI backend sends via
    boto3's invoke_agent_runtime(payload=...). We control its shape end to
    end (see app/routers/agent.py), so we can require whatever keys we want.

    This is an async generator, which BedrockAgentCoreApp turns into a
    streaming (text/event-stream) response automatically — each object we
    yield is serialized as one `data: <json>\\n\\n` SSE frame. Streaming lets
    the UI render the reply token-by-token with a typing indicator instead of
    waiting for the whole thing. The backend's non-streaming /agent/chat still
    works: it just concatenates every delta back into one string.
    """
    user_id = payload["user_id"]
    message = payload["prompt"]
    session_id = payload["session_id"]
    # Which assistant to run. This is read from the payload our FastAPI backend
    # sends, and the backend fills it from the caller's *verified* JWT role
    # claim — never from anything the client typed. Only our IAM-authenticated
    # backend can invoke this runtime, so trusting the payload here is safe.
    # Default to "customer": if the claim is ever missing, fall back to the
    # least-privileged agent rather than the admin one.
    role = payload.get("role", "customer")

    # Both builders wire an AgentCoreMemorySessionManager, which restores prior
    # conversation history for this session_id from AgentCore Memory (STM) on
    # construction and persists each new message back to it. History survives VM
    # recycles and cross-VM routing, unlike an in-process cache — so we can
    # safely build a fresh Agent on every invocation.
    if role == "admin":
        agent = build_admin_agent(user_id, session_id)
    else:
        agent = build_agent(user_id, session_id)

    # Strands yields many event types (tool use, lifecycle, etc.); we forward
    # only the text deltas (events carrying "data"). Wrapping each in a small
    # dict rather than yielding the bare string keeps the frame self-describing
    # and leaves room to add other frame types (e.g. errors) later without the
    # backend having to guess.
    async for event in agent.stream_async(message):
        if "data" in event:
            yield {"delta": event["data"]}


# AgentCore's container entrypoint runs this file directly (not through
# uvicorn/gunicorn), so app.run() is what actually starts the HTTP server.
if __name__ == "__main__":
    app.run()
