import json
import uuid
from collections.abc import Iterator
from typing import Annotated

import boto3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.security import TokenData, get_current_user
from app.schemas.agent import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])

# One client, reused across requests — boto3 clients are safe to share and
# creating one per-request would add unnecessary overhead.
_agentcore_client = boto3.client("bedrock-agentcore")


def _build_payload(current_user: TokenData, message: str, session_id: str) -> bytes:
    # role comes straight from the decoded JWT (get_current_user validated the
    # signature), not from the request body — the client can't choose which
    # assistant it talks to. The runtime uses this to pick the customer or admin
    # agent. Same endpoint for both, so nothing about the URL leaks which one a
    # caller reaches.
    return json.dumps(
        {
            "user_id": current_user.user_id,
            "role": current_user.role,
            "prompt": message,
            "session_id": session_id,
        }
    ).encode("utf-8")


def _iter_deltas(payload: bytes, session_id: str) -> Iterator[str]:
    """Invoke the runtime and yield the reply as it streams, chunk by chunk.

    The runtime returns a text/event-stream body — a sequence of
    `data: {"delta": "..."}` lines (see app/agent/runtime.py). boto3 hands us
    that body as a StreamingBody; iterating it reads incrementally rather than
    buffering the whole reply, which is the whole point of streaming.

    A blocking iterator on purpose: both callers hand this to Starlette's
    StreamingResponse (directly or after joining), and Starlette drives a sync
    generator on a threadpool, so it never stalls the event loop.
    """
    try:
        response = _agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=get_settings().agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=payload,
        )
    except _agentcore_client.exceptions.ClientError as exc:
        raise HTTPException(status_code=502, detail="Agent service unavailable") from exc

    for raw in response["response"].iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line.startswith("data: "):
            continue
        # Each frame is a JSON object. Ignore anything that isn't a text delta
        # (keeps us forward-compatible if the runtime adds other frame types).
        try:
            frame = json.loads(line[len("data: ") :])
        except json.JSONDecodeError:
            continue
        delta = frame.get("delta") if isinstance(frame, dict) else None
        if delta:
            yield delta


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> ChatResponse:
    """Non-streaming chat: wait for the whole reply, return it in one shot.

    Kept for callers that just want the final text (and for simplicity). The
    runtime streams regardless, so we concatenate the deltas back into one
    string here.
    """
    session_id = data.session_id or str(uuid.uuid4())
    payload = _build_payload(current_user, data.message, session_id)
    result = "".join(_iter_deltas(payload, session_id))
    return ChatResponse(result=result, session_id=session_id)


@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> StreamingResponse:
    """Streaming chat: forward the reply to the browser as it's generated.

    Emits Server-Sent Events. The first frame carries the session_id (so the
    client can continue the thread), then one frame per text delta, then a
    final done frame. Deltas are JSON-encoded so text containing newlines can't
    break SSE's line-based framing.
    """
    session_id = data.session_id or str(uuid.uuid4())
    payload = _build_payload(current_user, data.message, session_id)

    def event_stream() -> Iterator[str]:
        # Session id first, so the client can keep the conversation going.
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
        for delta in _iter_deltas(payload, session_id):
            yield f"data: {json.dumps(delta)}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # Defensive headers: stop proxies/browsers from buffering the stream,
        # which would defeat token-by-token rendering.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
