"""Offline ranking metrics. Relevance labels must come from an explicit eval set."""
from __future__ import annotations

import math


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    return sum(item in relevant_ids for item in ranked_ids[:k]) / k


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevant_ids:
        return 0.0
    return sum(item in relevant_ids for item in ranked_ids[:k]) / len(relevant_ids)


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    dcg = sum((1.0 / math.log2(rank + 2)) for rank, item in enumerate(ranked_ids[:k]) if item in relevant_ids)
    ideal_hits = min(k, len(relevant_ids))
    ideal = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
    return dcg / ideal if ideal else 0.0


def catalogue_coverage(recommended_ids: list[str], catalogue_size: int) -> float:
    if catalogue_size <= 0:
        return 0.0
    return len(set(recommended_ids)) / catalogue_size


def intra_list_diversity(genres_by_id: dict[str, set[str]], ranked_ids: list[str], k: int) -> float:
    selected = [genres_by_id.get(item, set()) for item in ranked_ids[:max(0, k)]]
    pairs = [(left, right) for index, left in enumerate(selected) for right in selected[index + 1:]]
    if not pairs:
        return 0.0
    distances = []
    for left, right in pairs:
        union = left | right
        distances.append(1.0 - len(left & right) / len(union) if union else 0.0)
    return sum(distances) / len(distances)


def novelty_at_k(popularity_by_id: dict[str, float], ranked_ids: list[str], k: int) -> float:
    values = [max(0.0, min(1.0, popularity_by_id[item])) for item in ranked_ids[:max(0, k)] if item in popularity_by_id]
    if not values:
        return 0.0
    return sum(-math.log2(max(value, 1e-9)) for value in values) / len(values)
