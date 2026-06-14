from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agentic import build_agentic_assignments, preflight_agentic_reading
from .dedup import apply_dedup_plan
from .downloads import reconcile_downloads
from .orchestrator import ensure_project, run_audit, scaffold_notes, score_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-reading")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create the workflow directory structure.")

    score = subparsers.add_parser("score-candidates", help="Score candidate papers from JSONL.")
    score.add_argument("--input", type=Path, default=Path("workspace/candidate_papers/candidates.jsonl"))
    score.add_argument("--output", type=Path, default=Path("workspace/candidate_papers/scored_candidates.jsonl"))

    notes = subparsers.add_parser("scaffold-notes", help="Create one Markdown note per scored paper.")
    notes.add_argument("--input", type=Path, default=Path("workspace/candidate_papers/scored_candidates.jsonl"))
    notes.add_argument("--force", action="store_true", help="Overwrite existing note files.")

    subparsers.add_parser("audit", help="Audit generated Markdown notes.")

    reconcile = subparsers.add_parser("reconcile-downloads", help="Rebuild compliant download records from candidates and local PDFs.")
    reconcile.add_argument("--candidates", type=Path, default=Path("workspace/candidate_papers/deduplicated_candidates.jsonl"))
    reconcile.add_argument("--records", type=Path, default=Path("workspace/download_queue/download_records.jsonl"), help="Input/output download records JSONL.")
    reconcile.add_argument("--no-parse-pages", action="store_true", help="Skip page parsing. This prevents PDFs from being counted as downloaded.")

    dedup = subparsers.add_parser("apply-dedup-plan", help="Mechanically apply a deduplication plan written by a dedup subagent.")
    dedup.add_argument("--candidates", type=Path, default=Path("workspace/candidate_papers/deduplicated_candidates.jsonl"))
    dedup.add_argument("--records", type=Path, default=Path("workspace/download_queue/download_records.jsonl"))
    dedup.add_argument("--plan", type=Path, default=Path("workspace/deep_reading_agentic/dedup_agent_plan.json"))
    dedup.add_argument("--report", type=Path, default=Path("workspace/deep_reading_agentic/dedup_apply_report.json"))

    assignments = subparsers.add_parser("build-agentic-assignments", help="Create one-paper-one-agent reading assignments from downloaded PDFs.")
    assignments.add_argument("--candidates", type=Path, default=Path("workspace/candidate_papers/deduplicated_candidates.jsonl"))
    assignments.add_argument("--records", type=Path, default=Path("workspace/download_queue/download_records.jsonl"))
    assignments.add_argument("--output", type=Path, default=Path("workspace/deep_reading_agentic/agentic_assignments.jsonl"))
    assignments.add_argument("--include-prompt-heavy", action="store_true", help="Include prompt-engineering-heavy papers in assignments.")
    assignments.add_argument("--archive-stale", action="store_true", help="Move stale per-assignment JSON files to stale_assignments/.")

    preflight = subparsers.add_parser("preflight-agentic-reading", help="Audit agentic assignments and PDF integrity before launching reader subagents.")
    preflight.add_argument("--candidates", type=Path, default=Path("workspace/candidate_papers/deduplicated_candidates.jsonl"))
    preflight.add_argument("--records", type=Path, default=Path("workspace/download_queue/download_records.jsonl"))
    preflight.add_argument("--assignments", type=Path, default=Path("workspace/deep_reading_agentic/agentic_assignments.jsonl"))
    preflight.add_argument("--archive-stale", action="store_true", help="Move stale per-assignment JSON files to stale_assignments/.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        return _run_command(args, root, parser)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_command(args: argparse.Namespace, root: Path, parser: argparse.ArgumentParser) -> int:

    if args.command == "init":
        ensure_project(root)
        print(f"initialized project at {root}")
        return 0
    if args.command == "score-candidates":
        count = score_candidates(root, _resolve(root, args.input), _resolve(root, args.output))
        print(f"scored {count} candidates")
        return 0
    if args.command == "scaffold-notes":
        result = scaffold_notes(root, _resolve(root, args.input), force=args.force)
        print(
            "processed {total} note scaffolds: created={created}, skipped={skipped}, overwritten={overwritten}".format(
                total=result.total,
                created=result.created,
                skipped=result.skipped,
                overwritten=result.overwritten,
            )
        )
        return 0
    if args.command == "audit":
        findings = run_audit(root)
        print(f"audit completed with {findings} findings")
        return 1 if findings else 0
    if args.command == "reconcile-downloads":
        result = reconcile_downloads(root, _resolve(root, args.candidates), _resolve(root, args.records), parse_pages=not args.no_parse_pages)
        print(
            "reconciled {records} download records: candidates={candidates}, downloaded={downloaded}, parse_verified={parse_verified}, unverified_local={unverified_local}".format(
                records=result.records,
                candidates=result.candidates,
                downloaded=result.downloaded,
                parse_verified=result.parse_verified,
                unverified_local=result.unverified_local,
            )
        )
        return 0
    if args.command == "apply-dedup-plan":
        result = apply_dedup_plan(
            root,
            _resolve(root, args.candidates),
            _resolve(root, args.records),
            _resolve(root, args.plan),
            _resolve(root, args.report),
        )
        print(
            "applied dedup plan: candidates {input_candidates}->{output_candidates}, records {input_download_records}->{output_download_records}, merge_ops={plan_merge_ops}".format(
                input_candidates=result.input_candidates,
                output_candidates=result.output_candidates,
                input_download_records=result.input_download_records,
                output_download_records=result.output_download_records,
                plan_merge_ops=result.plan_merge_ops,
            )
        )
        return 0
    if args.command == "build-agentic-assignments":
        result = build_agentic_assignments(
            root,
            _resolve(root, args.candidates),
            _resolve(root, args.records),
            _resolve(root, args.output),
            include_prompt_heavy=args.include_prompt_heavy,
            archive_stale=args.archive_stale,
        )
        print(
            "built {assignments} agentic assignments from {download_records} records; skipped_prompt_heavy={skipped_prompt_heavy}, stale_assignment_files={stale_assignment_files}".format(
                assignments=result.assignments,
                download_records=result.download_records,
                skipped_prompt_heavy=result.skipped_prompt_heavy,
                stale_assignment_files=result.stale_assignment_files,
            )
        )
        return 0
    if args.command == "preflight-agentic-reading":
        result = preflight_agentic_reading(
            root,
            _resolve(root, args.candidates),
            _resolve(root, args.records),
            _resolve(root, args.assignments),
            archive_stale=args.archive_stale,
        )
        print(
            "preflight checked {assignments} assignments: bad={bad_assignments}, stale_assignment_files={stale_assignment_files}, assignment_ready={assignment_ready}, workspace_clean={workspace_clean}".format(
                assignments=result.assignments,
                bad_assignments=result.bad_assignments,
                stale_assignment_files=result.stale_assignment_files,
                assignment_ready=result.assignment_ready,
                workspace_clean=result.workspace_clean,
            )
        )
        return 0 if result.assignment_ready else 1
    parser.error(f"unknown command: {args.command}")
    return 2


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path
