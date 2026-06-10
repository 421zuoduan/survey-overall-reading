import unittest

from paper_reading_system.models import CandidatePaper
from paper_reading_system.scoring import score_candidate, weighted_score


class ScoringTests(unittest.TestCase):
    def test_weighted_score_clamps_values(self):
        self.assertEqual(weighted_score({"x": 2.0, "y": -1.0}, {"x": 0.5, "y": 0.5}), 0.5)

    def test_foundational_candidate_becomes_must_read(self):
        candidate = CandidatePaper.from_json(
            {
                "identity": {
                    "title": "Attention Is All You Need",
                    "authors": ["Ashish Vaswani"],
                    "year": 2017,
                    "venue": "NeurIPS",
                },
                "raw_scores": {
                    "cross_review_recurrence": 0.9,
                    "structural_centrality": 0.9,
                    "citation_context_strength": 1.0,
                    "foundational_or_benchmark_role": 1.0,
                    "empirical_influence": 0.9,
                },
                "idea_scores": {
                    "evolution_chain_position": 1.0,
                    "methodological_transferability": 1.0,
                },
            }
        )
        scored = score_candidate(candidate)
        self.assertEqual(scored.tier, "Must-read")
        self.assertEqual(scored.confidence, "High")
        self.assertGreater(scored.selection_score, 0.6)

    def test_weak_candidate_is_low_confidence_context(self):
        candidate = CandidatePaper.from_json(
            {
                "identity": {"title": "Weak Background Paper"},
                "raw_scores": {"citation_context_strength": 0.05},
                "idea_scores": {},
            }
        )
        scored = score_candidate(candidate)
        self.assertEqual(scored.tier, "Context / background")
        self.assertEqual(scored.confidence, "Low")
        self.assertTrue(scored.needs_later_review)

    def test_prompt_engineering_heavy_candidate_is_excluded_from_deep_reading(self):
        candidate = CandidatePaper.from_json(
            {
                "identity": {"title": "Prompt Tricks for Everything", "authors": ["A. Author"], "year": 2024},
                "tags": ["prompt_engineering_heavy"],
                "raw_scores": {"citation_context_strength": 0.9, "prompt_engineering_dependency": 0.9},
                "idea_scores": {"frontier_relevance": 0.8},
            }
        )

        scored = score_candidate(candidate)

        self.assertTrue(scored.exclude_from_deep_reading)
        self.assertIn("prompt-engineering", scored.exclusion_reason)
        self.assertLess(scored.selection_score, 0.4)


if __name__ == "__main__":
    unittest.main()
