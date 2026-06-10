from __future__ import annotations

import argparse
from pathlib import Path

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()

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
    parser.error(f"unknown command: {args.command}")
    return 2


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path
