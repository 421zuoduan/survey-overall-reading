from __future__ import annotations

from typing import Any, Mapping


def validate_candidate_payload(data: Mapping[str, Any], source: str) -> None:
    if not isinstance(data, Mapping):
        raise ValueError(f"{source}: candidate row must be an object")

    identity = data.get("identity", data)
    if not isinstance(identity, Mapping):
        raise ValueError(f"{source}: identity must be an object")
    title = identity.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{source}: identity.title is required")

    _optional_string(data, "paper_id", source)
    _optional_string_list(data, "candidate_source", source)
    _optional_string_list(data, "tags", source)
    _score_map(data, "raw_scores", source)
    _score_map(data, "idea_scores", source)
    _score_map(data, "bonuses", source)
    _optional_number(data, "importance_score", source)
    _optional_number(data, "idea_generation_score", source)
    _optional_number(data, "selection_score", source)
    _optional_bool(data, "needs_later_review", source)
    _optional_bool(data, "exclude_from_deep_reading", source)
    _optional_string(data, "exclusion_reason", source)
    _evidence_list(data, source)

    if "authors" in identity and not _is_string_list(identity["authors"]):
        raise ValueError(f"{source}: identity.authors must be a list of strings")
    for key in ("venue", "doi", "arxiv"):
        _optional_string(identity, key, source, prefix="identity.")
    if "year" in identity and identity["year"] is not None:
        try:
            int(identity["year"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source}: identity.year must be an integer or null") from exc

    if "confidence" in data and data["confidence"] not in ("High", "Medium", "Low"):
        raise ValueError(f"{source}: confidence must be High, Medium, or Low")
    if "tier" in data and not isinstance(data["tier"], str):
        raise ValueError(f"{source}: tier must be a string")


def _score_map(data: Mapping[str, Any], key: str, source: str) -> None:
    if key not in data:
        return
    values = data[key]
    if not isinstance(values, Mapping):
        raise ValueError(f"{source}: {key} must be an object")
    for score_key, value in values.items():
        if not isinstance(score_key, str):
            raise ValueError(f"{source}: {key} keys must be strings")
        try:
            float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source}: {key}.{score_key} must be numeric") from exc


def _optional_string(data: Mapping[str, Any], key: str, source: str, prefix: str = "") -> None:
    if key in data and data[key] is not None and not isinstance(data[key], str):
        raise ValueError(f"{source}: {prefix}{key} must be a string")


def _optional_bool(data: Mapping[str, Any], key: str, source: str) -> None:
    if key in data and not isinstance(data[key], bool):
        raise ValueError(f"{source}: {key} must be a boolean")


def _optional_number(data: Mapping[str, Any], key: str, source: str) -> None:
    if key not in data:
        return
    try:
        float(data[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: {key} must be numeric") from exc


def _optional_string_list(data: Mapping[str, Any], key: str, source: str) -> None:
    if key in data and not _is_string_list(data[key]):
        raise ValueError(f"{source}: {key} must be a list of strings")


def _evidence_list(data: Mapping[str, Any], source: str) -> None:
    if "evidence" not in data:
        return
    evidence = data["evidence"]
    if not isinstance(evidence, list):
        raise ValueError(f"{source}: evidence must be a list")
    for index, item in enumerate(evidence):
        item_source = f"{source}: evidence[{index}]"
        if not isinstance(item, Mapping):
            raise ValueError(f"{item_source} must be an object")
        _optional_string(item, "dimension", item_source)
        _optional_number(item, "score", item_source)
        _optional_string(item, "source_review", item_source)
        _optional_string(item, "quote_or_anchor", item_source)
        _optional_string(item, "reason", item_source)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
