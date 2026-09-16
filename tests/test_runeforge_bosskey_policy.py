import json
import tempfile
import time
import unittest
from pathlib import Path

from core.agents.runeforge_agent import RuneforgeAgent


class RuneforgeBosskeyPolicyTests(unittest.TestCase):
    def _build_agent(self) -> RuneforgeAgent:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        os_dir = root / "Runeforge OS Edition"
        os_dir.mkdir(parents=True, exist_ok=True)
        (os_dir / "action_schema.json").write_text(
            json.dumps(
                {
                    "supported_action_types": ["move_file", "registry_edit", "close_app"],
                    "high_risk_action_types": ["move_file", "registry_edit", "close_app"],
                }
            ),
            encoding="utf-8",
        )
        return RuneforgeAgent(root=root)

    def tearDown(self) -> None:
        if hasattr(self, "tmp"):
            self.tmp.cleanup()

    def test_runeforge_high_risk_actions_require_command_code_not_bosskey(self) -> None:
        agent = self._build_agent()

        self.assertEqual(agent._bosskey_required_action_types(), set())
        self.assertIn("move_file", agent._command_code_required_action_types())
        self.assertIn("registry_edit", agent._command_code_required_action_types())

    def test_runeforge_requests_command_code_for_approved_high_risk_actions_when_missing(self) -> None:
        agent = self._build_agent()

        result = agent.run_os_action(
            {
                "action": {"action_type": "move_file", "params": {"source": "a", "destination": "b"}},
                "approved": True,
            }
        )

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("message"), "os action approval requested")
        self.assertTrue(result.get("pending", {}).get("requires_command_code"))


if __name__ == "__main__":
    unittest.main()
