import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import check_blocked_artifacts


class CheckBlockedArtifactsTests(unittest.TestCase):
    @patch("scripts.check_blocked_artifacts._candidate_files")
    def test_main_ok_for_clean_range(self, mock_candidates) -> None:
        mock_candidates.return_value = ["core/utils/bforge.py", "docs/architecture.md"]
        with patch("sys.argv", ["check_blocked_artifacts.py", "--range", "HEAD~1..HEAD"]):
            with redirect_stdout(io.StringIO()) as out:
                code = check_blocked_artifacts.main()
        self.assertEqual(code, 0)
        self.assertIn("Artifact guard: OK", out.getvalue())

    @patch("scripts.check_blocked_artifacts._candidate_files")
    def test_main_blocks_model_payloads(self, mock_candidates) -> None:
        mock_candidates.return_value = [
            "modules/runeforge_provider/models/Runeforge_Alpha-7b/tokenizer.json",
            "core/utils/bforge.py",
        ]
        with patch("sys.argv", ["check_blocked_artifacts.py"]):
            with redirect_stdout(io.StringIO()) as out:
                code = check_blocked_artifacts.main()
        self.assertEqual(code, 2)
        self.assertIn("blocked tracked artifacts found", out.getvalue())


if __name__ == "__main__":
    unittest.main()
