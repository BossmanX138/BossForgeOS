import os
import tempfile
import unittest
from pathlib import Path

from core.security_sentinel_agent import SecuritySentinelAgent


class SecuritySentinelTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_root = os.environ.get("BOSSFORGE_ROOT")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BOSSFORGE_ROOT"] = self.tmp.name

    def tearDown(self) -> None:
        self.tmp.cleanup()
        if self._old_root is None:
            os.environ.pop("BOSSFORGE_ROOT", None)
        else:
            os.environ["BOSSFORGE_ROOT"] = self._old_root

    def test_secret_roundtrip(self) -> None:
        agent = SecuritySentinelAgent(interval_seconds=1)
        saved = agent.set_secret("service_key", "abc12345")
        self.assertTrue(saved["ok"])

        listed = agent.list_secrets()
        self.assertIn("service_key", listed["secrets"])

        masked = agent.get_secret("service_key")
        self.assertTrue(masked["ok"])
        self.assertNotEqual(masked["value"], "abc12345")

        plain = agent.get_secret("service_key", reveal=True)
        self.assertEqual(plain["value"], "abc12345")

    def test_scan_workspace_finds_leak_patterns(self) -> None:
        root = Path(self.tmp.name)
        test_file = root / "leak_test.py"
        test_file.write_text('API_KEY = "AKIA1234567890ABCD12"\n', encoding="utf-8")

        agent = SecuritySentinelAgent(interval_seconds=1)
        result = agent.scan_workspace(str(root))
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["findings"]), 1)

    def test_policy_set_check(self) -> None:
        agent = SecuritySentinelAgent(interval_seconds=1)
        set_result = agent.set_policy("codemage", ["scan_workspace", "get_secret"])
        self.assertTrue(set_result["ok"])

        ok_check = agent.check_policy("codemage", "scan_workspace")
        self.assertTrue(ok_check["allowed"])

        no_check = agent.check_policy("codemage", "set_secret")
        self.assertFalse(no_check["allowed"])


if __name__ == "__main__":
    unittest.main()
