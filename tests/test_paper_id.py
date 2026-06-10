import unittest

from paper_reading_system.paper_id import generate_paper_id


class PaperIdTests(unittest.TestCase):
    def test_generates_stable_readable_id(self):
        first = generate_paper_id("Attention Is All You Need", ["Ashish Vaswani"], 2017)
        second = generate_paper_id("Attention Is All You Need", ["Ashish Vaswani"], 2017)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("2017-vaswani-attention-is-all-you-need-"))

    def test_requires_title(self):
        with self.assertRaises(ValueError):
            generate_paper_id("   ")


if __name__ == "__main__":
    unittest.main()
