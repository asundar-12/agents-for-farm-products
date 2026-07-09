from bedrock_agentcore.runtime import BedrockAgentCoreApp

from app.agent.main import build_agent

# BedrockAgentCoreApp is a small HTTP server AgentCore knows how to run inside
# the deployed container. It exposes POST /invocations (calls our entrypoint
# below) and GET /ping (health check) — we don't write either route ourselves.
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Called once per request to POST /invocations.

    `payload` is exactly the JSON body our FastAPI backend sends via
    boto3's invoke_agent_runtime(payload=...). We control its shape end to
    end (see app/routers/agent.py), so we can require whatever keys we want.
    """
    user_id = payload["user_id"]
    message = payload["prompt"]

    # Same build_agent() used by the local terminal REPL in main.py — the
    # agent's behavior (tools, system prompt, model) is identical whether it
    # runs on your laptop or inside AgentCore Runtime.
    agent = build_agent(user_id)
    result = agent(message)

    return {"result": str(result)}


# AgentCore's container entrypoint runs this file directly (not through
# uvicorn/gunicorn), so app.run() is what actually starts the HTTP server.
if __name__ == "__main__":
    app.run()
