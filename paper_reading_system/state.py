from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PAPER_STATES = [
    "discovered",
    "evidence_extracted",
    "scored",
    "normalized",
    "source_checked",
    "pdf_queued",
    "downloaded_or_link_only",
    "version_verified",
    "reading_assigned",
    "note_written",
    "audited",
    "idea_linked",
]


class WorkflowState:
    def __init__(self, root: Path):
        self.root = root
        self.db_path = root / "workspace" / "state" / "papers.sqlite"
        self.events_path = root / "workspace" / "state" / "workflow_events.jsonl"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def update_paper(self, paper_id: str, status: str, metadata: Dict[str, Any] | None = None) -> None:
        if status not in PAPER_STATES:
            raise ValueError(f"unknown paper status: {status}")
        current = self.get_paper_status(paper_id)
        if current and PAPER_STATES.index(status) < PAPER_STATES.index(current):
            raise ValueError(f"cannot move paper {paper_id} from {current} back to {status}")
        now = _utc_now()
        encoded = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into papers(paper_id, status, metadata_json, updated_at)
                values (?, ?, ?, ?)
                on conflict(paper_id) do update set
                  status=excluded.status,
                  metadata_json=excluded.metadata_json,
                  updated_at=excluded.updated_at
                """,
                (paper_id, status, encoded, now),
            )
        self.record_event("paper_status_updated", {"paper_id": paper_id, "status": status})

    def get_paper_status(self, paper_id: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("select status from papers where paper_id = ?", (paper_id,)).fetchone()
        return row[0] if row else None

    def record_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        row = {"timestamp": _utc_now(), "event_type": event_type, "payload": payload}
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                create table if not exists papers (
                  paper_id text primary key,
                  status text not null,
                  metadata_json text not null,
                  updated_at text not null
                )
                """
            )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
