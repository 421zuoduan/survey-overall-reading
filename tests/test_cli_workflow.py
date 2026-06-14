import json
import shutil
import tempfile
import unittest
from pathlib import Path

from paper_reading_system.cli import main
from paper_reading_system.orchestrator import scaffold_notes


class CliWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_score_notes_and_audit_workflow(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        input_path = candidate_dir / "candidates.jsonl"
        input_path.write_text(
            json.dumps(
                {
                    "identity": {
                        "title": "Attention Is All You Need",
                        "authors": ["Ashish Vaswani"],
                        "year": 2017,
                        "venue": "NeurIPS",
                    },
                    "raw_scores": {
                        "cross_review_recurrence": 0.9,
                        "structural_centrality": 0.95,
                        "citation_context_strength": 1.0,
                        "foundational_or_benchmark_role": 1.0,
                    },
                    "idea_scores": {"evolution_chain_position": 1.0},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        self.assertEqual(main(["--root", str(self.tmp), "init"]), 0)
        self.assertEqual(main(["--root", str(self.tmp), "score-candidates"]), 0)
        self.assertEqual(main(["--root", str(self.tmp), "scaffold-notes"]), 0)
        self.assertEqual(main(["--root", str(self.tmp), "audit"]), 1)
        self.assertTrue((self.tmp / "workspace" / "candidate_papers" / "scored_candidates.jsonl").exists())
        self.assertTrue((self.tmp / "reports" / "important_papers_ranked.md").exists())
        self.assertTrue((self.tmp / "notes" / "index.md").exists())
        self.assertEqual(len(list((self.tmp / "notes" / "deep_reading").glob("*.md"))), 1)
        self.assertTrue((self.tmp / "reports" / "qa_findings.md").exists())

    def test_missing_candidate_file_fails(self):
        self.assertEqual(main(["--root", str(self.tmp), "init"]), 0)
        self.assertEqual(main(["--root", str(self.tmp), "score-candidates"]), 1)

    def test_invalid_candidate_source_fails_validation(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        (candidate_dir / "candidates.jsonl").write_text(
            json.dumps(
                {
                    "identity": {"title": "Bad Candidate"},
                    "candidate_source": "review_citation",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self.assertEqual(main(["--root", str(self.tmp), "score-candidates"]), 1)

    def test_scaffold_notes_preserves_existing_file_without_force(self):
        self._write_single_candidate()
        self.assertEqual(main(["--root", str(self.tmp), "score-candidates"]), 0)
        result = scaffold_notes(self.tmp, self.tmp / "workspace" / "candidate_papers" / "scored_candidates.jsonl")
        self.assertEqual(result.created, 1)
        self.assertEqual(result.skipped, 0)
        note_path = next((self.tmp / "notes" / "deep_reading").glob("*.md"))
        note_path.write_text("manual reading work", encoding="utf-8")

        result = scaffold_notes(self.tmp, self.tmp / "workspace" / "candidate_papers" / "scored_candidates.jsonl")
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(note_path.read_text(encoding="utf-8"), "manual reading work")

        result = scaffold_notes(self.tmp, self.tmp / "workspace" / "candidate_papers" / "scored_candidates.jsonl", force=True)
        self.assertEqual(result.overwritten, 1)
        self.assertIn("# Attention Is All You Need", note_path.read_text(encoding="utf-8"))

    def test_duplicate_candidates_fail_during_scoring(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        row = {
            "identity": {
                "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani"],
                "year": 2017,
                "venue": "NeurIPS",
            },
            "raw_scores": {"citation_context_strength": 1.0},
        }
        (candidate_dir / "candidates.jsonl").write_text(
            json.dumps(row) + "\n" + json.dumps(row) + "\n",
            encoding="utf-8",
        )

        self.assertEqual(main(["--root", str(self.tmp), "score-candidates"]), 1)

    def test_duplicate_paper_id_with_different_titles_fails_in_scaffold(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        rows = [
            {
                "paper_id": "shared-id",
                "identity": {"title": "First Title", "authors": ["A"], "year": 2024},
                "raw_scores": {"citation_context_strength": 1.0},
            },
            {
                "paper_id": "shared-id",
                "identity": {"title": "Second Title", "authors": ["B"], "year": 2024},
                "raw_scores": {"citation_context_strength": 1.0},
            },
        ]
        (candidate_dir / "scored_candidates.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )

        self.assertEqual(main(["--root", str(self.tmp), "scaffold-notes"]), 1)

    def test_invalid_scored_candidate_fails_validation(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        (candidate_dir / "scored_candidates.jsonl").write_text(
            json.dumps({"identity": {"title": "Bad Scored"}, "evidence": ["not-an-object"]}) + "\n",
            encoding="utf-8",
        )

        self.assertEqual(main(["--root", str(self.tmp), "scaffold-notes"]), 1)

    def test_prompt_engineering_heavy_candidate_is_not_scaffolded(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        rows = [
            {
                "identity": {
                    "title": "A Mechanistic Paper",
                    "authors": ["A"],
                    "year": 2024,
                    "venue": "ICLR",
                },
                "raw_scores": {"citation_context_strength": 0.9},
            },
            {
                "identity": {
                    "title": "Prompt Tricks for Everything",
                    "authors": ["B"],
                    "year": 2024,
                    "venue": "ICLR",
                },
                "tags": ["prompt_engineering_heavy"],
                "raw_scores": {
                    "citation_context_strength": 0.9,
                    "prompt_engineering_dependency": 0.95,
                },
            },
        ]
        (candidate_dir / "candidates.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )

        self.assertEqual(main(["--root", str(self.tmp), "score-candidates"]), 0)
        result = scaffold_notes(self.tmp, self.tmp / "workspace" / "candidate_papers" / "scored_candidates.jsonl")

        self.assertEqual(result.total, 1)
        self.assertEqual(result.created, 1)
        notes = list((self.tmp / "notes" / "deep_reading").glob("*.md"))
        self.assertEqual(len(notes), 1)
        self.assertIn("mechanistic", notes[0].name)
        report = (self.tmp / "reports" / "important_papers_ranked.md").read_text(encoding="utf-8")
        self.assertIn("no: Mostly prompt-engineering-based contribution", report)

    def _write_single_candidate(self):
        candidate_dir = self.tmp / "workspace" / "candidate_papers"
        candidate_dir.mkdir(parents=True)
        input_path = candidate_dir / "candidates.jsonl"
        input_path.write_text(
            json.dumps(
                {
                    "identity": {
                        "title": "Attention Is All You Need",
                        "authors": ["Ashish Vaswani"],
                        "year": 2017,
                        "venue": "NeurIPS",
                    },
                    "raw_scores": {
                        "cross_review_recurrence": 0.9,
                        "structural_centrality": 0.95,
                        "citation_context_strength": 1.0,
                        "foundational_or_benchmark_role": 1.0,
                    },
                    "idea_scores": {"evolution_chain_position": 1.0},
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
