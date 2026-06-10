from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


ScoreMap = Dict[str, float]


@dataclass(frozen=True)
class PaperIdentity:
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    doi: str = ""
    arxiv: str = ""


@dataclass(frozen=True)
class CitationEvidence:
    dimension: str
    score: float
    source_review: str = ""
    quote_or_anchor: str = ""
    reason: str = ""


@dataclass
class CandidatePaper:
    paper_id: str
    identity: PaperIdentity
    candidate_source: List[str] = field(default_factory=lambda: ["review_citation"])
    raw_scores: ScoreMap = field(default_factory=dict)
    idea_scores: ScoreMap = field(default_factory=dict)
    bonuses: ScoreMap = field(default_factory=dict)
    evidence: List[CitationEvidence] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    exclude_from_deep_reading: bool = False
    exclusion_reason: str = ""
    confidence: str = "Medium"
    needs_later_review: bool = False
    tier: str = "Route-representative"
    importance_score: float = 0.0
    idea_generation_score: float = 0.0
    selection_score: float = 0.0

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "CandidatePaper":
        identity_data = data.get("identity") or data
        identity = PaperIdentity(
            title=str(identity_data.get("title", "")).strip(),
            authors=[str(author) for author in identity_data.get("authors", [])],
            year=_int_or_none(identity_data.get("year")),
            venue=str(identity_data.get("venue", "") or ""),
            doi=str(identity_data.get("doi", "") or ""),
            arxiv=str(identity_data.get("arxiv", "") or ""),
        )
        evidence = [
            CitationEvidence(
                dimension=str(item.get("dimension", "")),
                score=float(item.get("score", 0.0)),
                source_review=str(item.get("source_review", "") or ""),
                quote_or_anchor=str(item.get("quote_or_anchor", "") or ""),
                reason=str(item.get("reason", "") or ""),
            )
            for item in data.get("evidence", [])
        ]
        return cls(
            paper_id=str(data.get("paper_id", "") or ""),
            identity=identity,
            candidate_source=list(data.get("candidate_source", ["review_citation"])),
            raw_scores=_float_map(data.get("raw_scores", {})),
            idea_scores=_float_map(data.get("idea_scores", {})),
            bonuses=_float_map(data.get("bonuses", {})),
            evidence=evidence,
            tags=[str(tag) for tag in data.get("tags", [])],
            exclude_from_deep_reading=bool(data.get("exclude_from_deep_reading", False)),
            exclusion_reason=str(data.get("exclusion_reason", "") or ""),
            confidence=str(data.get("confidence", "Medium") or "Medium"),
            needs_later_review=bool(data.get("needs_later_review", False)),
            tier=str(data.get("tier", "Route-representative") or "Route-representative"),
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "identity": {
                "title": self.identity.title,
                "authors": self.identity.authors,
                "year": self.identity.year,
                "venue": self.identity.venue,
                "doi": self.identity.doi,
                "arxiv": self.identity.arxiv,
            },
            "candidate_source": self.candidate_source,
            "raw_scores": self.raw_scores,
            "idea_scores": self.idea_scores,
            "bonuses": self.bonuses,
            "evidence": [
                {
                    "dimension": item.dimension,
                    "score": item.score,
                    "source_review": item.source_review,
                    "quote_or_anchor": item.quote_or_anchor,
                    "reason": item.reason,
                }
                for item in self.evidence
            ],
            "tags": self.tags,
            "exclude_from_deep_reading": self.exclude_from_deep_reading,
            "exclusion_reason": self.exclusion_reason,
            "confidence": self.confidence,
            "needs_later_review": self.needs_later_review,
            "tier": self.tier,
            "importance_score": self.importance_score,
            "idea_generation_score": self.idea_generation_score,
            "selection_score": self.selection_score,
        }


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_map(values: Mapping[str, Any]) -> ScoreMap:
    return {str(key): float(value) for key, value in values.items()}


def as_jsonl(items: Iterable[CandidatePaper]) -> str:
    import json

    return "\n".join(json.dumps(item.to_json(), ensure_ascii=False, sort_keys=True) for item in items)
