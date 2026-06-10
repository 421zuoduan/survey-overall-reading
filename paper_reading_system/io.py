from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, Tuple

from .models import CandidatePaper


def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        raise FileNotFoundError(f"required JSONL input not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc


def read_jsonl_with_line(path: Path) -> Iterator[Tuple[int, dict]]:
    if not path.exists():
        raise FileNotFoundError(f"required JSONL input not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                yield line_number, json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def read_candidates(path: Path) -> list[CandidatePaper]:
    return [CandidatePaper.from_json(row) for row in read_jsonl(path)]


def write_candidates(path: Path, candidates: Iterable[CandidatePaper]) -> None:
    write_jsonl(path, (candidate.to_json() for candidate in candidates))
