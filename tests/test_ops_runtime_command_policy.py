import unittest

from modules.ops_runtime import api_adapter as ops_api


class OpsRuntimeCommandPolicyTests(unittest.TestCase):
    def test_validate_scheduler_command_allows_plain_command(self) -> None:
        ok, err = ops_api.validate_scheduler_command("python -m unittest")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_validate_scheduler_command_rejects_shell_controls(self) -> None:
        ok, err = ops_api.validate_scheduler_command("python -m unittest && whoami")
        self.assertFalse(ok)
        self.assertIn("forbidden shell control characters", err)

    def test_split_scheduler_command_handles_windows_tokens(self) -> None:
        parts = ops_api.split_scheduler_command('python -m unittest discover -s tests -p "test_*.py"')
        self.assertGreaterEqual(len(parts), 4)
        self.assertEqual(parts[0].lower(), "python")


if __name__ == "__main__":
    unittest.main()
