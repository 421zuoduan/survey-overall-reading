import unittest

from paper_reading_system.models import CandidatePaper
from paper_reading_system.notes import has_all_required_sections, render_note
from paper_reading_system.scoring import score_candidate


class NoteTests(unittest.TestCase):
    def test_rendered_note_has_required_sections(self):
        candidate = CandidatePaper.from_json(
            {
                "identity": {"title": "A Useful Paper", "authors": ["A. Author"], "year": 2024},
                "raw_scores": {"citation_context_strength": 0.7},
                "idea_scores": {"frontier_relevance": 0.8},
            }
        )
        note = render_note(score_candidate(candidate))
        self.assertTrue(has_all_required_sections(note))
        self.assertIn("## 11. 顶会 Idea 提炼", note)


if __name__ == "__main__":
    unittest.main()

