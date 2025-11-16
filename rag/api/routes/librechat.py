"""LibreChat-compatible OpenAI API endpoint for RAG integration."""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.graph.workflow import build_workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["librechat"])


# ============================================================================
# OpenAI-Compatible Request/Response Models
# ============================================================================

class ChatMessage(BaseModel):
    """OpenAI chat message format."""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request format."""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: bool = False
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    
    # RAG-specific options (optional, can be passed in metadata)
    rag_options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatCompletionChoice(BaseModel):
    """OpenAI choice format."""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI chat completion response format."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ChatCompletionChunk(BaseModel):
    """OpenAI streaming chunk format."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[Dict[str, Any]]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint for LibreChat integration.
    
    This endpoint accepts standard OpenAI chat format and returns RAG-enhanced
    responses using the building code knowledge base.
    
    Example LibreChat configuration in librechat.yaml:
    ```yaml
    endpoints:
      custom:
        - name: "Building Code RAG"
          apiKey: "user_provided"  # or your API key
          baseURL: "http://localhost:8000/v1"
          models:
            default: ["building-code-rag"]
          titleConvo: true
          titleModel: "building-code-rag"
          modelDisplayLabel: "Building Code Expert"
    ```
    """
    try:
        # Extract the user query from messages
        query = _extract_query_from_messages(request.messages)
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user message found in request"
            )
        
        # Run the RAG workflow
        workflow = build_workflow()
        state = {
            "query": query,
            "options": request.rag_options,
        }
        
        logger.info(f"Processing LibreChat query: {query[:100]}...")
        output = workflow.invoke(state)
        result = output.get("result")
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workflow did not return a result"
            )
        
        # Format response in OpenAI format
        answer = result.get("answer", "I couldn't find relevant information.")
        citations = result.get("citations", [])
        
        # Add citations to the answer
        formatted_answer = _format_answer_with_citations(answer, citations)
        
        # Estimate token usage (rough approximation)
        prompt_tokens = sum(len(msg.content.split()) for msg in request.messages) * 2
        completion_tokens = len(formatted_answer.split()) * 2
        
        response = ChatCompletionResponse(
            id=f"chatcmpl-{int(time.time())}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=formatted_answer
                    ),
                    finish_reason="stop"
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/models")
async def list_models():
    """
    List available models (LibreChat compatibility).
    
    Returns a single model representing the RAG system.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "building-code-rag",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "building-code-rag",
                "permission": [],
                "root": "building-code-rag",
                "parent": None,
            }
        ]
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_query_from_messages(messages: List[ChatMessage]) -> str:
    """
    Extract the user query from chat messages.
    
    Takes the last user message as the query. System messages are ignored
    for query extraction but could be used for additional context in the future.
    """
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    return ""


def _format_answer_with_citations(answer: str, citations: List[Dict[str, Any]]) -> str:
    """
    Format the answer with citations in a readable format.
    
    Appends citations at the end of the answer in a structured format
    that LibreChat can display nicely.
    """
    if not citations:
        return answer
    
    formatted = answer + "\n\n**Sources:**\n"
    for i, citation in enumerate(citations, 1):
        section_num = citation.get("section_number", "N/A")
        title = citation.get("title", "Unknown")
        chapter = citation.get("chapter", "N/A")
        page = citation.get("page", "N/A")
        
        formatted += f"\n{i}. Section {section_num}: {title}"
        if chapter != "N/A":
            formatted += f" (Chapter {chapter}"
            if page != "N/A":
                formatted += f", Page {page}"
            formatted += ")"
    
    return formatted
