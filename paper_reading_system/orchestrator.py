from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from .audit import audit_notes, render_findings
from .io import read_jsonl_with_line, write_candidates
from .models import CandidatePaper
from .notes import note_filename, write_note
from .scoring import score_candidate
from .state import WorkflowState
from .validation import validate_candidate_payload


class ScaffoldResult(NamedTuple):
    total: int
    created: int
    skipped: int
    overwritten: int


REQUIRED_DIRS = [
    "config/schemas",
    "config/agent_prompts",
    "inputs/reviews/pdf",
    "inputs/reviews/metadata",
    "workspace/extracted_reviews",
    "workspace/citation_graph",
    "workspace/candidate_papers",
    "workspace/top_conference_search",
    "workspace/download_queue",
    "workspace/cache/metadata",
    "workspace/cache/search_results",
    "workspace/cache/pdf_head_checks",
    "workspace/rate_limit",
    "workspace/state",
    "workspace/logs",
    "papers/pdf",
    "papers/metadata",
    "notes/deep_reading",
    "reports",
]


def ensure_project(root: Path) -> None:
    for name in REQUIRED_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    WorkflowState(root).record_event("project_initialized", {"root": str(root)})


def score_candidates(root: Path, input_path: Path, output_path: Path) -> int:
    state = WorkflowState(root)
    candidates = _read_validated_candidates(input_path)
    _ensure_unique_candidates(candidates)
    candidates.sort(key=lambda item: item.selection_score, reverse=True)
    write_candidates(output_path, candidates)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "important_papers_ranked.md").write_text(
        render_ranked_report(candidates),
        encoding="utf-8",
    )
    for candidate in candidates:
        state.update_paper(candidate.paper_id, "scored", candidate.to_json())
    return len(candidates)


def scaffold_notes(root: Path, scored_candidates_path: Path, force: bool = False) -> ScaffoldResult:
    state = WorkflowState(root)
    candidates = _read_validated_candidates(scored_candidates_path)
    readable_candidates = [candidate for candidate in candidates if not candidate.exclude_from_deep_reading]
    _ensure_unique_candidates(candidates)
    _ensure_unique_note_targets(readable_candidates)
    note_paths = []
    counts = {"created": 0, "skipped": 0, "overwritten": 0}
    for candidate in readable_candidates:
        path, action = write_note(root / "notes" / "deep_reading", candidate, force=force)
        counts[action] += 1
        note_paths.append(path)
        state.update_paper(candidate.paper_id, "note_written", {"note_path": str(path)})
    for candidate in candidates:
        if candidate.exclude_from_deep_reading:
            state.update_paper(
                candidate.paper_id,
                "audited",
                {"excluded_from_deep_reading": True, "reason": candidate.exclusion_reason},
            )
    (root / "notes").mkdir(parents=True, exist_ok=True)
    (root / "notes" / "index.md").write_text(render_notes_index(readable_candidates, note_paths), encoding="utf-8")
    return ScaffoldResult(
        total=len(readable_candidates),
        created=counts["created"],
        skipped=counts["skipped"],
        overwritten=counts["overwritten"],
    )


def run_audit(root: Path) -> int:
    notes = sorted((root / "notes" / "deep_reading").glob("*.md"))
    findings = audit_notes(notes)
    report = render_findings(findings)
    report_path = root / "reports" / "qa_findings.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    WorkflowState(root).record_event("audit_completed", {"findings": len(findings), "report": str(report_path)})
    return len(findings)


def render_ranked_report(candidates) -> str:
    lines = ["# Important Papers Ranked", ""]
    if not candidates:
        lines.append("No candidates scored yet.")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Rank | Paper | Year | Tier | Importance | Idea | Selection | Deep Reading | Confidence |",
            "|---:|---|---:|---|---:|---:|---:|---|---|",
        ]
    )
    for rank, candidate in enumerate(candidates, start=1):
        lines.append(
            "| {rank} | {title} | {year} | {tier} | {importance:.4f} | {idea:.4f} | {selection:.4f} | {deep_reading} | {confidence} |".format(
                rank=rank,
                title=_escape_table(candidate.identity.title),
                year=candidate.identity.year or "",
                tier=candidate.tier,
                importance=candidate.importance_score,
                idea=candidate.idea_generation_score,
                selection=candidate.selection_score,
                deep_reading=_deep_reading_status(candidate),
                confidence=candidate.confidence,
            )
        )
    lines.append("")
    lines.append("## Evidence Notes")
    lines.append("")
    for candidate in candidates:
        lines.append(f"### {candidate.identity.title}")
        if candidate.evidence:
            for item in candidate.evidence:
                lines.append(f"- {item.dimension}: score={item.score}; {item.reason or 'no reason recorded'}")
        else:
            lines.append("- No evidence packet entries recorded yet.")
        lines.append("")
    return "\n".join(lines)


def render_notes_index(candidates, note_paths) -> str:
    lines = ["# Deep Reading Notes Index", "", "<!-- Auto-generated by scaffold-notes. Do not edit manually. -->", ""]
    if not candidates:
        lines.append("No notes generated yet.")
        lines.append("")
        return "\n".join(lines)
    for candidate, path in zip(candidates, note_paths):
        lines.append(
            f"- [{candidate.identity.title}](deep_reading/{path.name}) - {candidate.tier}; selection={candidate.selection_score:.4f}; confidence={candidate.confidence}"
        )
    lines.append("")
    return "\n".join(lines)


def _escape_table(value: str) -> str:
    return str(value).replace("|", "\\|")


def _deep_reading_status(candidate) -> str:
    if not candidate.exclude_from_deep_reading:
        return "yes"
    return f"no: {_escape_table(candidate.exclusion_reason)}"


def _read_validated_candidates(path: Path):
    candidates = []
    for line_number, row in read_jsonl_with_line(path):
        validate_candidate_payload(row, f"{path}:{line_number}")
        candidates.append(score_candidate(CandidatePaper.from_json(row)))
    return candidates


def _ensure_unique_candidates(candidates) -> None:
    paper_ids = {}
    identities = {}
    for candidate in candidates:
        if candidate.paper_id in paper_ids:
            raise ValueError(f"duplicate paper_id {candidate.paper_id}")
        paper_ids[candidate.paper_id] = True

        identity_key = _identity_key(candidate)
        if identity_key in identities:
            raise ValueError(f"duplicate candidate identity for {candidate.paper_id}")
        identities[identity_key] = candidate.paper_id


def _ensure_unique_note_targets(candidates) -> None:
    seen_filenames = {}
    seen_paper_ids = {}
    for candidate in candidates:
        if candidate.paper_id in seen_paper_ids:
            raise ValueError(f"duplicate paper_id {candidate.paper_id}")
        seen_paper_ids[candidate.paper_id] = True

        filename = note_filename(candidate)
        if filename in seen_filenames:
            raise ValueError(f"duplicate note target for {candidate.paper_id}: {filename}")
        seen_filenames[filename] = candidate.paper_id


def _identity_key(candidate) -> tuple:
    authors = tuple(author.casefold().strip() for author in candidate.identity.authors)
    return (
        candidate.identity.title.casefold().strip(),
        authors,
        candidate.identity.year,
        candidate.identity.doi.casefold().strip(),
        candidate.identity.arxiv.casefold().strip(),
    )
