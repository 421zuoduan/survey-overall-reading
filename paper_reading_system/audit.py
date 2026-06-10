from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .notes import has_all_required_sections


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    message: str


def audit_notes(note_paths: Iterable[Path]) -> List[Finding]:
    findings: List[Finding] = []
    seen_names: set[str] = set()
    for path in note_paths:
        if path.name in seen_names:
            findings.append(Finding("MAJOR", str(path), "duplicate note filename"))
        seen_names.add(path.name)
        text = path.read_text(encoding="utf-8")
        if not has_all_required_sections(text):
            findings.append(Finding("MAJOR", str(path), "missing required deep-reading sections"))
        if "待补充" in text:
            findings.append(Finding("MINOR", str(path), "note still contains placeholder text"))
    return findings


def render_findings(findings: Iterable[Finding]) -> str:
    rows = list(findings)
    if not rows:
        return "# QA Findings\n\nNo issues found.\n"
    lines = ["# QA Findings", ""]
    for finding in rows:
        lines.append(f"- {finding.severity}: `{finding.path}` - {finding.message}")
    lines.append("")
    return "\n".join(lines)

