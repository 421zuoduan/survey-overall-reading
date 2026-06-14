from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, NamedTuple

from .downloads import record_rank
from .io import read_jsonl, write_jsonl
from .state import WorkflowState


class DedupApplyResult(NamedTuple):
    input_candidates: int
    output_candidates: int
    removed_candidates: int
    input_download_records: int
    output_download_records: int
    downloaded: int
    plan_merge_ops: int
    invalid_plan_items: int


def apply_dedup_plan(
    root: Path,
    candidates_path: Path | None = None,
    records_path: Path | None = None,
    plan_path: Path | None = None,
    report_path: Path | None = None,
) -> DedupApplyResult:
    candidates_path = candidates_path or root / "workspace" / "candidate_papers" / "deduplicated_candidates.jsonl"
    records_path = records_path or root / "workspace" / "download_queue" / "download_records.jsonl"
    plan_path = plan_path or root / "workspace" / "deep_reading_agentic" / "dedup_agent_plan.json"
    report_path = report_path or root / "workspace" / "deep_reading_agentic" / "dedup_apply_report.json"

    candidates = list(read_jsonl(candidates_path))
    records = list(read_jsonl(records_path)) if records_path.exists() else []
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    merge_ops = [item for item in plan if item.get("decision") == "merge"]
    validate_dedup_plan(candidates, merge_ops)

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_same_id: dict[str, int] = {}
    for row in candidates:
        paper_id = row["paper_id"]
        if paper_id in by_id:
            duplicate_same_id[paper_id] = duplicate_same_id.get(paper_id, 1) + 1
        else:
            by_id[paper_id] = row
    if duplicate_same_id:
        raise ValueError(
            "duplicate paper_id rows require an explicit dedup-agent plan before applying merges: "
            + ", ".join(sorted(duplicate_same_id))
        )

    removed: set[str] = set()
    pdf_relocations = []
    for op in merge_ops:
        canonical_id = op.get("canonical_paper_id")
        if not canonical_id or canonical_id not in by_id:
            continue
        for source_id in op.get("merge_from", []):
            if source_id not in by_id or source_id == canonical_id:
                continue
            by_id[canonical_id] = merge_candidate(by_id[canonical_id], by_id[source_id], op.get("reason", ""), float(op.get("confidence") or 0.0))
            relocation = copy_pdf_to_canonical(root, canonical_id, source_id)
            if relocation:
                pdf_relocations.append(relocation)
            removed.add(source_id)

    merged_candidates = [row for paper_id, row in by_id.items() if paper_id not in removed]
    merged_candidates.sort(key=lambda row: float(row.get("selection_score") or 0), reverse=True)
    write_jsonl(candidates_path, merged_candidates)

    candidate_ids = {row["paper_id"] for row in merged_candidates}
    merge_target_by_source = {
        source_id: op.get("canonical_paper_id")
        for op in merge_ops
        for source_id in op.get("merge_from", [])
        if op.get("canonical_paper_id")
    }
    record_by_id: dict[str, dict[str, Any]] = {}
    download_lineage_by_id: dict[str, list[dict[str, Any]]] = {paper_id: [] for paper_id in candidate_ids}
    for rec in records:
        rec = dict(rec)
        source_id = rec.get("paper_id")
        target = merge_target_by_source.get(source_id)
        if target:
            rec["paper_id"] = target
            rec.setdefault("source_paper_id", source_id)
        if rec.get("paper_id") not in candidate_ids:
            continue
        download_lineage_by_id.setdefault(rec["paper_id"], []).append(download_lineage_entry(rec, source_id))
        old = record_by_id.get(rec["paper_id"])
        if old is None or record_rank(rec) > record_rank(old):
            record_by_id[rec["paper_id"]] = rec
    for paper_id, lineage in download_lineage_by_id.items():
        if paper_id in record_by_id:
            record_by_id[paper_id]["download_lineage"] = lineage
            aliases = sorted({item["source_paper_id"] for item in lineage if item["source_paper_id"] != paper_id})
            if aliases:
                record_by_id[paper_id]["merged_download_records"] = aliases
    merged_records = sorted(record_by_id.values(), key=lambda row: (not row.get("downloaded", False), row["paper_id"]))
    write_jsonl(records_path, merged_records)
    write_jsonl(root / "workspace" / "download_queue" / "download_queue.jsonl", merged_records)

    report = {
        "input_candidates": len(candidates),
        "output_candidates": len(merged_candidates),
        "removed_candidate_ids": sorted(removed),
        "duplicate_same_id_groups": duplicate_same_id,
        "input_download_records": len(records),
        "output_download_records": len(merged_records),
        "downloaded": sum(1 for row in merged_records if row.get("downloaded")),
        "plan_merge_ops": len(merge_ops),
        "invalid_plan_items": 0,
        "pdf_relocations": pdf_relocations,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    WorkflowState(root).record_event("dedup_agent_plan_applied", report)
    return DedupApplyResult(
        input_candidates=len(candidates),
        output_candidates=len(merged_candidates),
        removed_candidates=len(removed),
        input_download_records=len(records),
        output_download_records=len(merged_records),
        downloaded=sum(1 for row in merged_records if row.get("downloaded")),
        plan_merge_ops=len(merge_ops),
        invalid_plan_items=0,
    )


def validate_dedup_plan(candidates: list[dict[str, Any]], merge_ops: list[dict[str, Any]]) -> None:
    candidate_ids = {row["paper_id"] for row in candidates}
    errors = []
    seen_sources: dict[str, str] = {}
    for index, op in enumerate(merge_ops, start=1):
        canonical_id = op.get("canonical_paper_id")
        if not canonical_id:
            errors.append(f"merge op {index} missing canonical_paper_id")
            continue
        if canonical_id not in candidate_ids:
            errors.append(f"merge op {index} canonical_paper_id not found: {canonical_id}")
        for source_id in op.get("merge_from", []):
            if source_id not in candidate_ids:
                errors.append(f"merge op {index} source paper_id not found: {source_id}")
            if source_id == canonical_id:
                errors.append(f"merge op {index} lists canonical in merge_from: {source_id}")
            if source_id in seen_sources and seen_sources[source_id] != canonical_id:
                errors.append(f"source paper_id {source_id} is merged into multiple canonicals")
            seen_sources[source_id] = canonical_id
    if errors:
        raise ValueError("invalid dedup-agent plan: " + "; ".join(errors))


def merge_candidate(canonical: dict[str, Any], other: dict[str, Any], reason: str, confidence: float) -> dict[str, Any]:
    out = dict(canonical)
    ci = dict(out.get("identity", {}))
    oi = other.get("identity", {})
    for key in ["title", "authors", "year", "venue", "doi", "arxiv"]:
        ci[key] = _better_value(ci.get(key), oi.get(key))
    out["identity"] = ci
    for key in ["candidate_source", "tags", "cited_by_reviews"]:
        out[key] = sorted(set(out.get(key, []) + other.get(key, [])))
    out["review_occurrences"] = out.get("review_occurrences", []) + other.get("review_occurrences", [])
    out["citation_context_count"] = int(out.get("citation_context_count") or 0) + int(other.get("citation_context_count") or 0)
    for key in ["selection_score", "importance_score", "idea_generation_score"]:
        out[key] = max(float(out.get(key) or 0), float(other.get(key) or 0))
    out["evidence"] = out.get("evidence", []) + other.get("evidence", [])
    existing_record = out.get("download_record") or {}
    other_record = other.get("download_record") or {}
    if record_rank(other_record) > record_rank(existing_record):
        out["download_record"] = normalize_embedded_download_record(other_record, canonical["paper_id"], other["paper_id"])
    elif existing_record:
        out["download_record"] = normalize_embedded_download_record(existing_record, canonical["paper_id"], existing_record.get("paper_id", canonical["paper_id"]))
    out.setdefault("merged_from", [])
    out["merged_from"].append(
        {
            "paper_id": other["paper_id"],
            "title": oi.get("title", ""),
            "doi": oi.get("doi", ""),
            "arxiv": oi.get("arxiv", ""),
            "reason": reason,
            "confidence": confidence,
        }
    )
    out.setdefault("version_relations", [])
    out["version_relations"].append(
        {
            "related_paper_id": other["paper_id"],
            "relation": "same_work_merged",
            "reason": reason,
            "confidence": confidence,
        }
    )
    return out


def normalize_embedded_download_record(record: dict[str, Any], canonical_id: str, source_id: str) -> dict[str, Any]:
    out = dict(record)
    original_id = out.get("paper_id") or source_id
    out["paper_id"] = canonical_id
    if original_id != canonical_id:
        out["source_paper_id"] = original_id
    return out


def download_lineage_entry(record: dict[str, Any], source_id: str | None) -> dict[str, Any]:
    return {
        "source_paper_id": source_id or record.get("paper_id", ""),
        "canonical_paper_id": record.get("paper_id", ""),
        "source_url": record.get("source_url", ""),
        "source_type": record.get("source_type", "unknown"),
        "local_path": record.get("local_path", ""),
        "downloaded": bool(record.get("downloaded")),
        "version_match_confidence": record.get("version_match_confidence", 0.0),
        "pdf_sha256": record.get("pdf_sha256", ""),
        "rank": record_rank(record),
    }


def copy_pdf_to_canonical(root: Path, canonical_id: str, source_id: str) -> dict[str, str] | None:
    canonical_pdf = root / "papers" / "pdf" / f"{canonical_id}.pdf"
    source_pdf = root / "papers" / "pdf" / f"{source_id}.pdf"
    if source_pdf.exists() and not canonical_pdf.exists():
        canonical_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pdf, canonical_pdf)
        return {"from": str(source_pdf), "to": str(canonical_pdf), "action": "copy_for_canonical_id"}
    return None


def _better_value(current: Any, new: Any) -> Any:
    if current in (None, "", [], {}):
        return new
    return current
