import json
import uuid
from typing import Annotated

import boto3
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.security import TokenData, get_current_user
from app.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])

# One client, reused across requests — boto3 clients are safe to share and
# creating one per-request would add unnecessary overhead.
_agentcore_client = boto3.client("bedrock-agentcore")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> ChatResponse:
    settings = get_settings()
    session_id = data.session_id or str(uuid.uuid4())

    # role comes straight from the decoded JWT (get_current_user validated the
    # signature), not from the request body — the client can't choose which
    # assistant it talks to. The runtime uses this to pick the customer or admin
    # agent. Same endpoint for both, so nothing about the URL leaks which one a
    # caller reaches.
    payload = json.dumps(
        {
            "user_id": current_user.user_id,
            "role": current_user.role,
            "prompt": data.message,
            "session_id": session_id,
        }
    ).encode("utf-8")

    try:
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=settings.agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=payload,
        )
    except _agentcore_client.exceptions.ClientError as exc:
        raise HTTPException(status_code=502, detail="Agent service unavailable") from exc

    body = json.loads(response["response"].read())
    return ChatResponse(result=body["result"], session_id=session_id)
