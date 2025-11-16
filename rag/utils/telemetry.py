"""Weights & Biases telemetry helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict

import wandb

from rag.config import settings

_EVENT_INDEX = 0


@lru_cache(maxsize=1)
def _get_run():
    if not settings.wandb_enabled or not settings.wandb_project:
        return None
    run = wandb.init(
        project=settings.wandb_project,
        entity=settings.wandb_entity,
        name=settings.wandb_run_name,
        reinit=True,
        config={
            "chat_model": settings.chat_model,
            "embedding_model": settings.embedding_model,
            "search_top_k": settings.top_k_sections,
        },
    )
    return run


def log_event(step: str, payload: Dict[str, Any] | None = None) -> None:
    run = _get_run()
    if run is None:
        return
    payload = payload or {}
    numeric_payload = {f"{step}/{key}": value for key, value in payload.items() if isinstance(value, (int, float))}
    text_payload = {
        f"{step}/text": json.dumps(payload, ensure_ascii=False)
    } if payload else {}

    global _EVENT_INDEX
    _EVENT_INDEX += 1
    wandb.log({**numeric_payload, **text_payload}, step=_EVENT_INDEX)
