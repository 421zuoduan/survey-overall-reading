from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, NamedTuple

from .io import read_jsonl, write_jsonl
from .state import WorkflowState


MAX_PDF_BYTES = 150_000_000
PDF_TAIL_BYTES = 4096


class ReconcileResult(NamedTuple):
    candidates: int
    records: int
    downloaded: int
    unverified_local: int
    parse_verified: int


def record_rank(record: dict[str, Any]) -> tuple:
    return (
        bool(record.get("downloaded")),
        bool(record.get("source_url")) and record.get("source_type") != "unknown",
        bool(record.get("can_download")),
        float(record.get("version_match_confidence") or 0.0),
        int(record.get("file_size") or 0),
    )


def source_record_rank(record: dict[str, Any]) -> tuple:
    provenance = record.get("source_provenance", "")
    traceable = bool(record.get("source_url")) and record.get("source_type") != "unknown"
    return (
        traceable,
        provenance == "candidate_download_record",
        provenance == "previous_download_record",
        bool(record.get("can_download")),
        float(record.get("version_match_confidence") or 0.0),
        int(record.get("file_size") or 0),
    )


def pdf_integrity_check(path: Path, parse_pages: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "sha256": "",
        "header_ok": False,
        "eof_ok": False,
        "parse_ok": False,
        "parse_checked": False,
        "pages": 0,
        "risk_flags": [],
    }
    if not path.exists():
        result["risk_flags"].append("missing_file")
        return result

    with path.open("rb") as handle:
        result["header_ok"] = handle.read(5) == b"%PDF-"
        handle.seek(max(0, result["size"] - PDF_TAIL_BYTES))
        result["eof_ok"] = b"%%EOF" in handle.read()

    if result["size"] == 35_000_000:
        result["risk_flags"].append("exact_old_35mb_cap")
    if result["size"] >= MAX_PDF_BYTES:
        result["risk_flags"].append("near_or_above_150mb_cap")

    if parse_pages:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            result["parse_checked"] = True
            result["pages"] = len(reader.pages)
            result["parse_ok"] = result["pages"] > 0
        except ModuleNotFoundError:
            result["parse_checked"] = False
            result["risk_flags"].append("parse_not_checked:pypdf_missing")
        except Exception as exc:  # pragma: no cover - exact parser exception is file-dependent.
            result["parse_checked"] = True
            result["risk_flags"].append(f"parse_failed:{type(exc).__name__}")

    if result["header_ok"] and result["eof_ok"] and result["parse_ok"]:
        result["sha256"] = sha256_file(path)
    else:
        if not result["header_ok"]:
            result["risk_flags"].append("bad_pdf_header")
        if not result["eof_ok"]:
            result["risk_flags"].append("missing_eof_marker")
        if result["parse_checked"] and not result["parse_ok"]:
            result["risk_flags"].append("not_parseable")
        if not result["parse_checked"]:
            result["risk_flags"].append("parse_not_checked")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconcile_downloads(
    root: Path,
    candidates_path: Path | None = None,
    records_path: Path | None = None,
    parse_pages: bool = True,
) -> ReconcileResult:
    candidates_path = candidates_path or root / "workspace" / "candidate_papers" / "deduplicated_candidates.jsonl"
    records_path = records_path or root / "workspace" / "download_queue" / "download_records.jsonl"
    candidates = list(read_jsonl(candidates_path))
    previous_records = {row["paper_id"]: row for row in read_jsonl(records_path)} if records_path.exists() else {}
    run_date = dt.date.today().isoformat()
    state = WorkflowState(root)

    records_by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        paper_id = candidate["paper_id"]
        identity = candidate.get("identity", {})
        pdf_path = root / "papers" / "pdf" / f"{paper_id}.pdf"
        embedded = candidate.get("download_record") or {}
        previous = previous_records.get(paper_id) or {}
        source = _best_source_record(embedded, previous, identity)
        for lineage_key in ["download_lineage", "merged_download_records", "source_paper_id"]:
            if previous.get(lineage_key) and not source.get(lineage_key):
                source[lineage_key] = previous[lineage_key]
        check = pdf_integrity_check(pdf_path, parse_pages=parse_pages)

        has_traceable_source = (
            bool(source.get("source_url"))
            and source.get("source_type") != "unknown"
            and source.get("source_provenance") in {"candidate_download_record", "previous_download_record"}
        )
        file_integrity_ok = bool(check["exists"] and check["header_ok"] and check["eof_ok"] and check["parse_checked"] and check["parse_ok"])
        verified_pdf = has_traceable_source and file_integrity_ok

        reason = source.get("reason") or "No legal OA PDF source verified in this run; metadata/link-only retained."
        if verified_pdf:
            reason = f"{reason} Local PDF present and integrity checked."
        elif check["exists"] and not has_traceable_source:
            reason = f"{reason} Local PDF exists, but source URL/type is not traceable; not counted as compliant downloaded PDF."
        elif check["exists"] and not file_integrity_ok:
            reason = f"{reason} Local PDF exists, but integrity checks failed: {', '.join(check['risk_flags'])}."

        record = {
            "paper_id": paper_id,
            "title": identity.get("title", ""),
            "source_url": source.get("source_url", ""),
            "source_type": source.get("source_type", "unknown"),
            "access_status": _verified_access_status(source) if verified_pdf else source.get("access_status", "metadata_only"),
            "license": source.get("license", ""),
            "access_date": run_date,
            "can_download": bool(source.get("can_download", False) or verified_pdf),
            "can_text_mine": source.get("can_text_mine", "unknown"),
            "source_provenance": source.get("source_provenance", "none"),
            "action": "download_pdf" if verified_pdf else source.get("action", "save_link_only"),
            "reason": reason,
            "version_match_confidence": float(source.get("version_match_confidence") or (0.80 if verified_pdf else 0.0)),
            "downloaded": verified_pdf,
            "local_path": str(pdf_path) if verified_pdf else "",
            "unverified_local_path": str(pdf_path) if check["exists"] and not verified_pdf else "",
            "file_size": check["size"],
            "pdf_header_ok": check["header_ok"],
            "pdf_eof_ok": check["eof_ok"],
            "pdf_parse_ok": check["parse_ok"],
            "pdf_parse_checked": check["parse_checked"],
            "pdf_sha256": check["sha256"],
            "pdf_validation_level": "parse_verified" if verified_pdf else ("header_eof_only" if check["header_ok"] and check["eof_ok"] else "unverified"),
            "pdf_risk_flags": check["risk_flags"],
        }
        for lineage_key in ["download_lineage", "merged_download_records", "source_paper_id"]:
            if source.get(lineage_key):
                record[lineage_key] = source[lineage_key]
        old = records_by_id.get(paper_id)
        if old is None or record_rank(record) > record_rank(old):
            records_by_id[paper_id] = record

        write_metadata_file(root, candidate, record)
        _safe_update(state, paper_id, "downloaded_or_link_only", {"downloaded": verified_pdf, "source_url": record["source_url"]})

    records = sorted(records_by_id.values(), key=lambda row: (not row.get("downloaded", False), row["paper_id"]))
    out_path = records_path
    write_jsonl(out_path, records)
    default_queue_path = root / "workspace" / "download_queue" / "download_queue.jsonl"
    if out_path == root / "workspace" / "download_queue" / "download_records.jsonl":
        write_jsonl(default_queue_path, records)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "missing_papers.md").write_text(render_missing(records), encoding="utf-8")
    (root / "reports" / "retrieval_coverage_report.md").write_text(render_retrieval_coverage(records), encoding="utf-8")
    (root / "reports" / "compliance_and_version_audit.md").write_text(render_compliance(records), encoding="utf-8")
    state.record_event(
        "downloads_reconciled",
        {"candidates": len(candidates), "records": len(records), "downloaded": sum(1 for row in records if row.get("downloaded"))},
    )
    return ReconcileResult(
        candidates=len(candidates),
        records=len(records),
        downloaded=sum(1 for row in records if row.get("downloaded")),
        unverified_local=sum(1 for row in records if row.get("unverified_local_path")),
        parse_verified=sum(1 for row in records if row.get("downloaded") and row.get("pdf_parse_ok")),
    )


def write_metadata_file(root: Path, candidate: dict[str, Any], record: dict[str, Any]) -> None:
    out = root / "papers" / "metadata" / f"{candidate['paper_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {}
    if out.exists():
        try:
            metadata = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
    metadata.setdefault("paper_id", candidate["paper_id"])
    metadata.setdefault("identity", candidate.get("identity", {}))
    metadata["metadata_status"] = "downloaded" if record.get("downloaded") else "metadata_or_link_only"
    retrieval = dict(metadata.get("retrieval") or {})
    history = list(metadata.get("retrieval_history") or [])
    if retrieval:
        history.append({"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "retrieval": retrieval})
        metadata["retrieval_history"] = history[-20:]
    retrieval.update(
        {
            "best_pdf_url": record.get("source_url", ""),
            "source_type": record.get("source_type", "unknown"),
            "local_pdf": record.get("local_path", ""),
            "unverified_local_pdf": record.get("unverified_local_path", ""),
            "version_match_confidence": record.get("version_match_confidence", 0.0),
            "pdf_validation_level": record.get("pdf_validation_level", "unverified"),
            "source_provenance": record.get("source_provenance", "none"),
            "reconciled": True,
        }
    )
    metadata["retrieval"] = retrieval
    out.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def render_missing(records: Iterable[dict[str, Any]]) -> str:
    rows = [row for row in records if not row.get("downloaded")]
    lines = ["# Missing / Link-Only Papers", "", f"Total missing or unverified: {len(rows)}", ""]
    if rows:
        lines += ["| Paper ID | Title | Source Type | Reason |", "|---|---|---|---|"]
        for row in rows:
            lines.append(
                "| {paper_id} | {title} | {source_type} | {reason} |".format(
                    paper_id=_escape(row.get("paper_id", "")),
                    title=_escape(row.get("title", "")),
                    source_type=_escape(row.get("source_type", "")),
                    reason=_escape(row.get("reason", "")),
                )
            )
    lines.append("")
    return "\n".join(lines)


def render_retrieval_coverage(records: Iterable[dict[str, Any]]) -> str:
    rows = list(records)
    downloaded = sum(1 for row in rows if row.get("downloaded"))
    parse_verified = sum(1 for row in rows if row.get("downloaded") and row.get("pdf_parse_ok"))
    link_only = len(rows) - downloaded
    lines = [
        "# Retrieval Coverage Report",
        "",
        f"- Total records: {len(rows)}",
        f"- Verified downloaded PDFs: {downloaded}",
        f"- Parse-verified downloaded PDFs: {parse_verified}",
        f"- Link-only / missing / unverified: {link_only}",
        f"- Coverage: {(downloaded / len(rows) * 100):.1f}%" if rows else "- Coverage: 0.0%",
        "",
        "## Source Type Counts",
        "",
    ]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("source_type") or "unknown"] = counts.get(row.get("source_type") or "unknown", 0) + 1
    for source_type, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {source_type}: {count}")
    lines.append("")
    return "\n".join(lines)


def render_compliance(records: Iterable[dict[str, Any]]) -> str:
    rows = list(records)
    findings: list[str] = []
    for row in rows:
        if row.get("downloaded") and (not row.get("source_url") or row.get("source_type") == "unknown"):
            findings.append(f"- `{row.get('paper_id')}` downloaded without traceable source.")
        if row.get("downloaded") and not row.get("pdf_parse_ok"):
            findings.append(f"- `{row.get('paper_id')}` downloaded without parse-verified PDF.")
        if row.get("unverified_local_path"):
            findings.append(f"- `{row.get('paper_id')}` has local PDF but is unverified: {row.get('unverified_local_path')}")
        if row.get("pdf_risk_flags"):
            findings.append(f"- `{row.get('paper_id')}` PDF risk flags: {', '.join(row.get('pdf_risk_flags', []))}")
    lines = [
        "# Compliance and Version Audit",
        "",
        f"- Records audited: {len(rows)}",
        f"- Downloaded with traceable source: {sum(1 for row in rows if row.get('downloaded'))}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(findings or ["- No compliance findings in reconciled records."])
    lines.append("")
    return "\n".join(lines)


def _best_source_record(embedded: dict[str, Any], previous: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    if embedded:
        row = dict(embedded)
        row["source_provenance"] = "candidate_download_record"
        candidates.append(row)
    if previous:
        row = dict(previous)
        row["source_provenance"] = row.get("source_provenance") or "previous_download_record"
        candidates.append(row)
    if identity.get("arxiv"):
        candidates.append(
            {
                "source_url": f"https://arxiv.org/pdf/{identity['arxiv']}.pdf",
                "source_type": "arxiv",
                "access_status": "preprint",
                "can_download": True,
                "action": "download_pdf",
                "reason": "arXiv identifier extracted from candidate identity; source inference only, not sufficient to verify a local PDF.",
                "version_match_confidence": 0.90,
                "source_provenance": "identity_arxiv_inferred",
            }
        )
    return max((row for row in candidates if row), key=source_record_rank, default={})


def _verified_access_status(record: dict[str, Any]) -> str:
    if record.get("source_type") == "arxiv":
        return "preprint"
    return record.get("access_status") if record.get("access_status") not in ("", "metadata_only") else "open_access"


def _safe_update(state: WorkflowState, paper_id: str, status: str, metadata: dict[str, Any]) -> None:
    try:
        state.update_paper(paper_id, status, metadata)
    except ValueError as exc:
        state.record_event("paper_status_update_skipped", {"paper_id": paper_id, "status": status, "reason": str(exc)})


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
