"""Ranking utilities for retrieval."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[Tuple[int, float]]],
    *,
    k: int = 60,
) -> Dict[int, float]:
    """Compute Reciprocal Rank Fusion (RRF) scores."""

    scores: Dict[int, float] = defaultdict(float)
    for result_list in ranked_lists:
        for rank, (item_id, _) in enumerate(result_list):
            scores[item_id] += 1.0 / (k + rank + 1)
    return scores
