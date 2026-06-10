from __future__ import annotations

from typing import Mapping

from .models import CandidatePaper
from .paper_id import generate_paper_id


IMPORTANCE_WEIGHTS = {
    "cross_review_recurrence": 0.25,
    "structural_centrality": 0.20,
    "citation_context_strength": 0.20,
    "foundational_or_benchmark_role": 0.15,
    "empirical_influence": 0.10,
    "recency_leverage": 0.05,
    "limitation_or_controversy_value": 0.05,
}

IDEA_WEIGHTS = {
    "unresolved_bottleneck_signal": 0.25,
    "evolution_chain_position": 0.20,
    "frontier_relevance": 0.15,
    "methodological_transferability": 0.15,
    "benchmark_or_metric_shift": 0.10,
    "feasibility_of_minimal_experiment": 0.10,
    "reviewer_interest_risk_balance": 0.05,
}

SELECTION_WEIGHTS = {"importance_score": 0.65, "idea_generation_score": 0.35}
PROMPT_ENGINEERING_TAG = "prompt_engineering_heavy"


def weighted_score(scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("weights must have a positive total")
    value = sum(_clamp(scores.get(key, 0.0)) * weight for key, weight in weights.items()) / total_weight
    return round(value, 4)


def score_candidate(candidate: CandidatePaper) -> CandidatePaper:
    if not candidate.paper_id:
        candidate.paper_id = generate_paper_id(
            candidate.identity.title,
            candidate.identity.authors,
            candidate.identity.year,
        )

    candidate.importance_score = weighted_score(candidate.raw_scores, IMPORTANCE_WEIGHTS)
    candidate.idea_generation_score = weighted_score(candidate.idea_scores, IDEA_WEIGHTS)
    base_selection = (
        SELECTION_WEIGHTS["importance_score"] * candidate.importance_score
        + SELECTION_WEIGHTS["idea_generation_score"] * candidate.idea_generation_score
    )
    if is_prompt_engineering_heavy(candidate):
        candidate.exclude_from_deep_reading = True
        candidate.exclusion_reason = "Mostly prompt-engineering-based contribution; record metadata but skip deep reading."
        base_selection *= 0.25
        candidate.bonuses["prompt_engineering_penalty"] = min(candidate.bonuses.get("prompt_engineering_penalty", 0.0), -0.20)
    candidate.selection_score = round(_clamp(base_selection + sum(candidate.bonuses.values())), 4)
    candidate.tier = infer_tier(candidate)
    candidate.confidence = infer_confidence(candidate)
    candidate.needs_later_review = candidate.needs_later_review or candidate.confidence == "Low"
    return candidate


def is_prompt_engineering_heavy(candidate: CandidatePaper) -> bool:
    if candidate.exclude_from_deep_reading:
        return True
    tags = {tag.casefold().strip() for tag in candidate.tags}
    if PROMPT_ENGINEERING_TAG in tags:
        return True
    score = candidate.raw_scores.get("prompt_engineering_dependency", 0.0)
    return score >= 0.70


def infer_tier(candidate: CandidatePaper) -> str:
    raw = candidate.raw_scores
    idea = candidate.idea_scores
    if candidate.importance_score >= 0.85 or raw.get("foundational_or_benchmark_role", 0.0) >= 0.9:
        return "Must-read"
    if raw.get("structural_centrality", 0.0) >= 0.75 and idea.get("evolution_chain_position", 0.0) >= 0.75:
        return "Evolution-chain"
    if candidate.idea_generation_score >= 0.72 and "top_conference_supplement" in candidate.candidate_source:
        return "Watch / frontier"
    if candidate.importance_score < 0.35 and raw.get("citation_context_strength", 0.0) < 0.35:
        return "Context / background"
    return "Route-representative"


def infer_confidence(candidate: CandidatePaper) -> str:
    raw = candidate.raw_scores
    has_strong_context = raw.get("citation_context_strength", 0.0) >= 0.7
    has_recurrence = raw.get("cross_review_recurrence", 0.0) >= 0.65
    has_identity = bool(candidate.identity.doi or candidate.identity.arxiv or candidate.identity.venue)
    if has_strong_context and has_recurrence and has_identity:
        return "High"
    if candidate.identity.title and (has_strong_context or has_identity):
        return "Medium"
    return "Low"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
