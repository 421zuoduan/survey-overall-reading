import shutil
import tempfile
import unittest
from pathlib import Path

from paper_reading_system.state import WorkflowState


class WorkflowStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_rejects_status_regression(self):
        state = WorkflowState(self.tmp)
        state.update_paper("paper-1", "scored")
        state.update_paper("paper-1", "note_written")

        with self.assertRaises(ValueError):
            state.update_paper("paper-1", "scored")

        self.assertEqual(state.get_paper_status("paper-1"), "note_written")

    def test_allows_same_state_update(self):
        state = WorkflowState(self.tmp)
        state.update_paper("paper-1", "scored", {"first": True})
        state.update_paper("paper-1", "scored", {"first": False})
        self.assertEqual(state.get_paper_status("paper-1"), "scored")


if __name__ == "__main__":
    unittest.main()

