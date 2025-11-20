"""OpenAI-compatible chat completions endpoint for LibreChat integration."""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.graph.workflow import build_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"])
RAG_API_KEY = os.getenv("RAG_API_KEY")


def _verify_api_key(authorization: Optional[str]) -> None:
    """Enforce optional bearer auth for LibreChat/OpenAI-compatible requests."""
    if not RAG_API_KEY:
        return

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")

    scheme, _, candidate = authorization.partition(" ")
    if scheme.lower() != "bearer" or candidate != RAG_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., pattern="^(system|user|assistant|developer)$")
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request."""

    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = 0.0
    presence_penalty: Optional[float] = 0.0


class ChatCompletionChoice(BaseModel):
    """Chat completion choice."""

    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ModelInfo(BaseModel):
    """Model information."""

    id: str
    object: str = "model"
    created: int
    owned_by: str = "custom"


class ModelsListResponse(BaseModel):
    """Models list response."""

    object: str = "list"
    data: List[ModelInfo]


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest, authorization: Optional[str] = Header(default=None)
):
    """
    OpenAI-compatible chat completions endpoint.

    Extracts the user's last message and runs it through the RAG workflow.
    Compatible with LibreChat and other OpenAI-compatible clients.
    Supports both streaming and non-streaming responses.
    """
    _verify_api_key(authorization)
    logger.info(f"Received chat completion request for model: {request.model}")

    # Get last user message
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        # Fallback to last message
        query = request.messages[-1].content if request.messages else "Hello"
    else:
        query = user_messages[-1].content

    logger.info(f"Processing query: {query[:100]}... (streaming={request.stream})")

    try:
        # Run RAG workflow
        workflow = build_workflow()
        result = workflow.invoke({"query": query, "options": {}})

        answer = result.get("result", {}).get("answer", "")

        if not answer:
            answer = "I apologize, but I couldn't generate an answer to your question."

        # Calculate approximate token usage (rough estimate: ~1 token per word)
        prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
        completion_tokens = len(answer.split())

        # Check if streaming is requested
        if request.stream:
            # Return streaming response
            async def generate_stream():
                import json

                # Preserve whitespace (including newlines) to keep markdown intact
                tokens = [token for token in re.split(r"(\s+)", answer) if token]
                for i, token in enumerate(tokens):
                    chunk = {
                        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None if i < len(tokens) - 1 else "stop",
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Send final done message
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # Return non-streaming response
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                created=int(time.time()),
                model=request.model,
                choices=[
                    ChatCompletionChoice(
                        message=ChatMessage(role="assistant", content=answer),
                        finish_reason="stop",
                    )
                ],
                usage=ChatCompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )

            logger.info(f"Generated response with {completion_tokens} tokens")
            return response

    except Exception as e:
        logger.error(f"Error processing chat completion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}",
        )


@router.get("/models", response_model=ModelsListResponse)
async def list_models(authorization: Optional[str] = Header(default=None)) -> ModelsListResponse:
    """List available models for LibreChat/OpenAI-compatible clients."""
    _verify_api_key(authorization)
    return ModelsListResponse(
        object="list",
        data=[
            ModelInfo(
                id="building-code-rag",
                object="model",
                created=int(time.time()),
                owned_by="custom",
            )
        ],
    )
