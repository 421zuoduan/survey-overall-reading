import json
import shutil
import tempfile
import unittest
from pathlib import Path

from paper_reading_system.agentic import build_agentic_assignments, preflight_agentic_reading
from paper_reading_system.cli import main
from paper_reading_system.dedup import apply_dedup_plan
from paper_reading_system.downloads import reconcile_downloads


class ProductionToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_reconcile_recovers_candidate_source_and_counts_verified_pdf(self):
        paper_id = "2024-smith-traceable-paper"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [
                {
                    "paper_id": paper_id,
                    "identity": {"title": "Traceable Paper", "authors": ["Jane Smith"], "year": 2024},
                    "download_record": {
                        "source_url": "https://arxiv.org/pdf/2401.00001.pdf",
                        "source_type": "arxiv",
                        "access_status": "preprint",
                        "can_download": True,
                        "action": "download_pdf",
                        "version_match_confidence": 0.91,
                    },
                }
            ],
        )
        self._write_pdf(self.tmp / "papers/pdf" / f"{paper_id}.pdf")

        result = reconcile_downloads(self.tmp)
        records = self._read_jsonl(self.tmp / "workspace/download_queue/download_records.jsonl")

        self.assertEqual(result.downloaded, 1)
        self.assertEqual(result.parse_verified, 1)
        self.assertEqual(records[0]["source_type"], "arxiv")
        self.assertTrue(records[0]["downloaded"])
        self.assertFalse(records[0]["unverified_local_path"])

    def test_reconcile_does_not_count_untraceable_local_pdf(self):
        paper_id = "2024-smith-untraceable-paper"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [{"paper_id": paper_id, "identity": {"title": "Untraceable Paper", "authors": ["Jane Smith"], "year": 2024}}],
        )
        self._write_pdf(self.tmp / "papers/pdf" / f"{paper_id}.pdf")

        result = reconcile_downloads(self.tmp)
        records = self._read_jsonl(self.tmp / "workspace/download_queue/download_records.jsonl")

        self.assertEqual(result.downloaded, 0)
        self.assertEqual(result.unverified_local, 1)
        self.assertFalse(records[0]["downloaded"])
        self.assertIn("not traceable", records[0]["reason"])

    def test_reconcile_identity_arxiv_alone_does_not_verify_local_pdf(self):
        paper_id = "2024-smith-arxiv-only-paper"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [{"paper_id": paper_id, "identity": {"title": "Arxiv Only Paper", "authors": ["Jane Smith"], "year": 2024, "arxiv": "2401.00003"}}],
        )
        self._write_pdf(self.tmp / "papers/pdf" / f"{paper_id}.pdf")

        result = reconcile_downloads(self.tmp)
        records = self._read_jsonl(self.tmp / "workspace/download_queue/download_records.jsonl")

        self.assertEqual(result.downloaded, 0)
        self.assertEqual(records[0]["source_provenance"], "identity_arxiv_inferred")
        self.assertFalse(records[0]["downloaded"])

    def test_apply_dedup_plan_merges_only_agent_approved_pairs(self):
        canonical_id = "2024-smith-memory-system"
        source_id = "2024-smith-memory-systems"
        separate_id = "2024-smith-memory-benchmark"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [
                {"paper_id": canonical_id, "identity": {"title": "Memory System", "authors": ["Jane Smith"], "year": 2024}, "selection_score": 0.7},
                {"paper_id": source_id, "identity": {"title": "Memory Systems", "authors": ["Jane Smith"], "year": 2024}, "selection_score": 0.8},
                {"paper_id": separate_id, "identity": {"title": "Memory Benchmark", "authors": ["Jane Smith"], "year": 2024}, "selection_score": 0.9},
            ],
        )
        self._write_jsonl(
            self.tmp / "workspace/download_queue/download_records.jsonl",
            [
                {"paper_id": canonical_id, "downloaded": False, "source_type": "unknown"},
                {"paper_id": source_id, "downloaded": True, "source_url": "https://arxiv.org/pdf/1.pdf", "source_type": "arxiv", "can_download": True, "version_match_confidence": 0.9, "file_size": 100},
                {"paper_id": separate_id, "downloaded": False, "source_type": "unknown"},
            ],
        )
        plan_path = self.tmp / "workspace/deep_reading_agentic/dedup_agent_plan.json"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            json.dumps(
                [
                    {
                        "decision": "merge",
                        "canonical_paper_id": canonical_id,
                        "merge_from": [source_id],
                        "reason": "same work per dedup subagent",
                        "confidence": 0.95,
                    },
                    {"decision": "keep_separate", "canonical_paper_id": separate_id, "merge_from": []},
                ]
            ),
            encoding="utf-8",
        )

        result = apply_dedup_plan(self.tmp)
        candidates = self._read_jsonl(self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl")
        records = self._read_jsonl(self.tmp / "workspace/download_queue/download_records.jsonl")

        self.assertEqual(result.output_candidates, 2)
        self.assertEqual({row["paper_id"] for row in candidates}, {canonical_id, separate_id})
        canonical_record = next(row for row in records if row["paper_id"] == canonical_id)
        self.assertTrue(canonical_record["downloaded"])
        self.assertEqual(canonical_record["merged_download_records"], [source_id])
        self.assertEqual(canonical_record["download_lineage"][1]["source_paper_id"], source_id)

    def test_apply_dedup_plan_rejects_invalid_source(self):
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [{"paper_id": "canonical", "identity": {"title": "Canonical"}}],
        )
        self._write_jsonl(self.tmp / "workspace/download_queue/download_records.jsonl", [])
        plan_path = self.tmp / "workspace/deep_reading_agentic/dedup_agent_plan.json"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            json.dumps([{"decision": "merge", "canonical_paper_id": "canonical", "merge_from": ["missing-source"]}]),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "invalid dedup-agent plan"):
            apply_dedup_plan(self.tmp)

    def test_build_assignments_and_preflight_detect_stale_files(self):
        paper_id = "2024-smith-readable-paper"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [{"paper_id": paper_id, "identity": {"title": "Readable Paper", "authors": ["Jane Smith"], "year": 2024}, "selection_score": 0.8}],
        )
        pdf_path = self.tmp / "papers/pdf" / f"{paper_id}.pdf"
        self._write_pdf(pdf_path)
        self._write_jsonl(
            self.tmp / "workspace/download_queue/download_records.jsonl",
            [
                {
                    "paper_id": paper_id,
                    "title": "Readable Paper",
                    "downloaded": True,
                    "local_path": str(pdf_path),
                    "pdf_validation_level": "parse_verified",
                    "pdf_parse_ok": True,
                    "source_url": "https://arxiv.org/pdf/2401.00002.pdf",
                    "source_type": "arxiv",
                }
            ],
        )
        build = build_agentic_assignments(self.tmp)
        stale = self.tmp / "workspace/deep_reading_agentic/assignments/stale-paper.json"
        stale.write_text("{}", encoding="utf-8")
        preflight = preflight_agentic_reading(self.tmp, archive_stale=False)

        self.assertEqual(build.assignments, 1)
        self.assertEqual(preflight.assignments, 1)
        self.assertEqual(preflight.stale_assignment_files, 1)
        self.assertFalse(preflight.assignment_ready)
        self.assertFalse(preflight.workspace_clean)

    def test_build_assignments_archives_stale_only_with_flag(self):
        paper_id = "2024-smith-readable-paper"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [{"paper_id": paper_id, "identity": {"title": "Readable Paper"}, "selection_score": 0.8}],
        )
        pdf_path = self.tmp / "papers/pdf" / f"{paper_id}.pdf"
        self._write_pdf(pdf_path)
        self._write_jsonl(
            self.tmp / "workspace/download_queue/download_records.jsonl",
            [
                {
                    "paper_id": paper_id,
                    "title": "Readable Paper",
                    "downloaded": True,
                    "local_path": str(pdf_path),
                    "pdf_validation_level": "parse_verified",
                    "pdf_parse_ok": True,
                }
            ],
        )
        stale = self.tmp / "workspace/deep_reading_agentic/assignments/stale-paper.json"
        stale.parent.mkdir(parents=True)
        stale.write_text("{}", encoding="utf-8")

        no_archive = build_agentic_assignments(self.tmp)
        self.assertEqual(no_archive.stale_assignment_files, 1)
        self.assertTrue(stale.exists())

        archived = build_agentic_assignments(self.tmp, archive_stale=True)
        self.assertEqual(archived.stale_assignment_files, 0)
        self.assertFalse(stale.exists())

    def test_reconcile_cli_writes_custom_records_path(self):
        paper_id = "2024-smith-custom-records"
        self._write_jsonl(
            self.tmp / "workspace/candidate_papers/deduplicated_candidates.jsonl",
            [{"paper_id": paper_id, "identity": {"title": "Custom Records"}}],
        )
        out = self.tmp / "custom" / "records.jsonl"

        self.assertEqual(main(["--root", str(self.tmp), "reconcile-downloads", "--records", str(out)]), 0)
        self.assertTrue(out.exists())

    def _write_jsonl(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def _read_jsonl(self, path):
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_pdf(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=10, height=10)
        with path.open("wb") as handle:
            writer.write(handle)


if __name__ == "__main__":
    unittest.main()
