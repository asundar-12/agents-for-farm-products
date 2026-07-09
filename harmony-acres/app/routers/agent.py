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

    payload = json.dumps(
        {"user_id": current_user.user_id, "prompt": data.message}
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
