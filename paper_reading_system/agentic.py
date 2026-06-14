from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, NamedTuple

from .downloads import pdf_integrity_check
from .io import read_jsonl, write_jsonl
from .state import WorkflowState


class AssignmentBuildResult(NamedTuple):
    candidates: int
    download_records: int
    assignments: int
    skipped_prompt_heavy: int
    stale_assignment_files: int


class PreflightResult(NamedTuple):
    candidates: int
    download_records: int
    downloaded: int
    assignments: int
    assignment_files: int
    stale_assignment_files: int
    stale_metadata_files: int
    stale_pdf_files: int
    bad_assignments: int
    assignment_ready: bool
    workspace_clean: bool
    all_assignments_ready: bool


def build_agentic_assignments(
    root: Path,
    candidates_path: Path | None = None,
    records_path: Path | None = None,
    assignments_path: Path | None = None,
    include_prompt_heavy: bool = False,
    archive_stale: bool = False,
) -> AssignmentBuildResult:
    candidates_path = candidates_path or root / "workspace" / "candidate_papers" / "deduplicated_candidates.jsonl"
    records_path = records_path or root / "workspace" / "download_queue" / "download_records.jsonl"
    assignments_path = assignments_path or root / "workspace" / "deep_reading_agentic" / "agentic_assignments.jsonl"
    candidates = list(read_jsonl(candidates_path))
    records = list(read_jsonl(records_path))
    candidate_by_id = {row["paper_id"]: row for row in candidates}
    downloaded_records = [
        row
        for row in records
        if row.get("downloaded") and row.get("pdf_validation_level") == "parse_verified" and row.get("pdf_parse_ok")
    ]

    assignments = []
    skipped_prompt_heavy = 0
    for rank, record in enumerate(downloaded_records, start=1):
        candidate = candidate_by_id.get(record["paper_id"])
        if not candidate:
            continue
        if not include_prompt_heavy and _is_prompt_heavy(candidate):
            skipped_prompt_heavy += 1
            continue
        identity = candidate.get("identity", {})
        paper_id = record["paper_id"]
        title = identity.get("title") or record.get("title") or paper_id
        assignments.append(
            {
                "paper_id": paper_id,
                "title": title,
                "rank": rank,
                "score": candidate.get("selection_score", 0),
                "tier": candidate.get("tier", ""),
                "pdf": record.get("local_path") or str(root / "papers" / "pdf" / f"{paper_id}.pdf"),
                "metadata": str(Path("papers") / "metadata" / f"{paper_id}.json"),
                "source_url": record.get("source_url", ""),
                "source_type": record.get("source_type", ""),
                "output_note": str(Path("notes") / "deep_reading_agentic" / f"{paper_id}__{_short_title(title)}.md"),
                "status": "pending",
            }
        )

    assignments.sort(key=lambda row: (-float(row.get("score") or 0), row["paper_id"]))
    assignments_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(assignments_path, assignments)
    assignments_dir = assignments_path.parent / "assignments"
    stale_assignment_files = count_stale_assignment_files(assignments_dir, {row["paper_id"] for row in assignments})
    if archive_stale:
        archive_stale_assignment_files(assignments_dir, {row["paper_id"] for row in assignments}, assignments_path.parent / "stale_assignments")
        stale_assignment_files = 0
    assignments_dir.mkdir(parents=True, exist_ok=True)
    for assignment in assignments:
        (assignments_dir / f"{assignment['paper_id']}.json").write_text(
            json.dumps(assignment, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    WorkflowState(root).record_event(
        "agentic_assignments_built",
        {"assignments": len(assignments), "skipped_prompt_heavy": skipped_prompt_heavy, "include_prompt_heavy": include_prompt_heavy},
    )
    return AssignmentBuildResult(
        candidates=len(candidates),
        download_records=len(records),
        assignments=len(assignments),
        skipped_prompt_heavy=skipped_prompt_heavy,
        stale_assignment_files=stale_assignment_files,
    )


def preflight_agentic_reading(
    root: Path,
    candidates_path: Path | None = None,
    records_path: Path | None = None,
    assignments_path: Path | None = None,
    archive_stale: bool = False,
) -> PreflightResult:
    candidates_path = candidates_path or root / "workspace" / "candidate_papers" / "deduplicated_candidates.jsonl"
    records_path = records_path or root / "workspace" / "download_queue" / "download_records.jsonl"
    assignments_path = assignments_path or root / "workspace" / "deep_reading_agentic" / "agentic_assignments.jsonl"
    candidates = list(read_jsonl(candidates_path))
    records = list(read_jsonl(records_path))
    assignments = list(read_jsonl(assignments_path))
    candidate_ids = {row["paper_id"] for row in candidates}
    record_ids = {row["paper_id"] for row in records}
    downloaded_ids = {row["paper_id"] for row in records if row.get("downloaded")}
    assignment_ids = [row["paper_id"] for row in assignments]
    assignment_id_set = set(assignment_ids)

    assignments_dir = assignments_path.parent / "assignments"
    if archive_stale:
        archive_stale_assignment_files(assignments_dir, assignment_id_set, assignments_path.parent / "stale_assignments")
    assignment_files = sorted(assignments_dir.glob("*.json")) if assignments_dir.exists() else []
    stale_assignment_files = [str(path) for path in assignment_files if path.stem not in assignment_id_set]
    stale_metadata = [str(path) for path in (root / "papers" / "metadata").glob("*.json") if path.stem not in candidate_ids]
    stale_pdfs = [str(path) for path in (root / "papers" / "pdf").glob("*.pdf") if path.stem not in candidate_ids]

    bad_assignments = []
    seen: set[str] = set()
    pdf_checks = []
    for assignment in assignments:
        paper_id = assignment["paper_id"]
        if paper_id in seen:
            bad_assignments.append({"paper_id": paper_id, "reason": "duplicate_assignment"})
        seen.add(paper_id)
        pdf_path = _resolve_path(root, assignment.get("pdf", ""))
        check = pdf_integrity_check(pdf_path, parse_pages=True)
        check["paper_id"] = paper_id
        check["source_url"] = assignment.get("source_url", "")
        check["source_type"] = assignment.get("source_type", "")
        pdf_checks.append(check)
        if paper_id not in candidate_ids or paper_id not in record_ids or paper_id not in downloaded_ids:
            bad_assignments.append({"paper_id": paper_id, "reason": "not present in candidate/downloaded record sets"})
        if check["risk_flags"]:
            bad_assignments.append({"paper_id": paper_id, "reason": ",".join(check["risk_flags"])})

    copied_pdf_checks = copied_canonical_pdf_checks(root)
    assignment_ready = not bad_assignments and not stale_assignment_files
    workspace_clean = assignment_ready and not stale_metadata and not stale_pdfs
    report = {
        "candidate_count": len(candidates),
        "download_record_count": len(records),
        "downloaded_count": len(downloaded_ids),
        "assignment_count": len(assignments),
        "assignment_file_count": len(assignment_files),
        "stale_assignment_files": stale_assignment_files,
        "stale_metadata_files": stale_metadata,
        "stale_pdf_files": stale_pdfs,
        "bad_assignments": bad_assignments,
        "pdf_checks": pdf_checks,
        "copied_pdf_checks": copied_pdf_checks,
        "assignment_ready": assignment_ready,
        "workspace_clean": workspace_clean,
        "all_assignments_ready": assignment_ready,
    }
    out_json = assignments_path.parent / "preflight_agentic_reading_report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "agentic_reading_preflight.md").write_text(render_agentic_preflight_markdown(report), encoding="utf-8")
    WorkflowState(root).record_event("agentic_reading_preflight_completed", {"assignments": len(assignments), "bad_assignments": len(bad_assignments)})
    return PreflightResult(
        candidates=len(candidates),
        download_records=len(records),
        downloaded=len(downloaded_ids),
        assignments=len(assignments),
        assignment_files=len(assignment_files),
        stale_assignment_files=len(stale_assignment_files),
        stale_metadata_files=len(stale_metadata),
        stale_pdf_files=len(stale_pdfs),
        bad_assignments=len(bad_assignments),
        assignment_ready=bool(report["assignment_ready"]),
        workspace_clean=bool(report["workspace_clean"]),
        all_assignments_ready=bool(report["all_assignments_ready"]),
    )


def count_stale_assignment_files(assignments_dir: Path, active_ids: set[str]) -> int:
    if not assignments_dir.exists():
        return 0
    return sum(1 for path in assignments_dir.glob("*.json") if path.stem not in active_ids)


def archive_stale_assignment_files(assignments_dir: Path, active_ids: set[str], stale_dir: Path) -> int:
    if not assignments_dir.exists():
        return 0
    stale_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for path in sorted(assignments_dir.glob("*.json")):
        if path.stem not in active_ids:
            target = stale_dir / path.name
            shutil.move(str(path), str(target))
            moved += 1
    return moved


def copied_canonical_pdf_checks(root: Path) -> list[dict[str, Any]]:
    dedup_report_path = root / "workspace" / "deep_reading_agentic" / "dedup_apply_report.json"
    if not dedup_report_path.exists():
        return []
    report = json.loads(dedup_report_path.read_text(encoding="utf-8"))
    checks = []
    for item in report.get("pdf_relocations", []):
        target = Path(item["to"])
        checks.append({"from": item["from"], "to": item["to"], "target_check": pdf_integrity_check(target, parse_pages=True)})
    return checks


def render_agentic_preflight_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agentic Reading Preflight",
        "",
        "## Summary",
        "",
        f"- Candidates: {report['candidate_count']}",
        f"- Download records: {report['download_record_count']}",
        f"- Downloaded records: {report['downloaded_count']}",
        f"- Assignment rows: {report['assignment_count']}",
        f"- Assignment files: {report['assignment_file_count']}",
        f"- Assignment ready: {report['assignment_ready']}",
        f"- Workspace clean: {report['workspace_clean']}",
        f"- All assignments ready: {report['all_assignments_ready']}",
        "",
        "## Stale Artifacts",
        "",
        f"- Stale assignment files: {len(report['stale_assignment_files'])}",
        f"- Stale metadata files: {len(report['stale_metadata_files'])}",
        f"- Stale PDF files: {len(report['stale_pdf_files'])}",
        "",
    ]
    for title, key in [
        ("Stale Assignment Files", "stale_assignment_files"),
        ("Stale Metadata Files", "stale_metadata_files"),
        ("Stale PDF Files", "stale_pdf_files"),
    ]:
        if report[key]:
            lines += [f"### {title}", ""]
            for path in report[key][:80]:
                lines.append(f"- `{path}`")
            if len(report[key]) > 80:
                lines.append(f"- ... {len(report[key]) - 80} more")
            lines.append("")
    lines += ["## Assignment / PDF Risks", ""]
    if report["bad_assignments"]:
        for item in report["bad_assignments"][:120]:
            lines.append(f"- `{item['paper_id']}`: {item['reason']}")
        if len(report["bad_assignments"]) > 120:
            lines.append(f"- ... {len(report['bad_assignments']) - 120} more")
    else:
        lines.append("- No assignment-level PDF risks found.")
    lines += ["", "## Copied Canonical PDF Checks", ""]
    if report["copied_pdf_checks"]:
        for item in report["copied_pdf_checks"]:
            check = item["target_check"]
            lines.append(
                f"- `{item['from']}` -> `{item['to']}`: pages={check['pages']}, sha256={check['sha256'][:16]}, risks={', '.join(check['risk_flags']) or 'none'}"
            )
    else:
        lines.append("- No copied canonical PDFs recorded.")
    lines.append("")
    return "\n".join(lines)


def _is_prompt_heavy(candidate: dict[str, Any]) -> bool:
    tags = set(candidate.get("tags") or [])
    raw_scores = candidate.get("raw_scores") or {}
    return "prompt_engineering_heavy" in tags or float(raw_scores.get("prompt_engineering_dependency") or 0.0) >= 0.70


def _short_title(title: str) -> str:
    import re

    words = re.findall(r"[A-Za-z0-9]+", title.lower())[:10]
    return "-".join(words) or "untitled"


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
