import tempfile
import unittest
from pathlib import Path

from core.devlot_agent import DevlotAgent


class DevlotAgentTests(unittest.TestCase):
    def test_status_ping_emits_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = DevlotAgent(root=root)
            agent.handle_command({"target": "devlot", "command": "status_ping", "args": {}})

            latest = agent.bus.read_latest_events(limit=5)
            self.assertTrue(any(item.get("source") == "devlot" and item.get("event") == "command:status_ping" for item in latest))

    def test_reset_workspace_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = DevlotAgent(root=root)
            agent.handle_command({"target": "devlot", "command": "reset_workspace", "args": {}})

            latest = agent.bus.read_latest_events(limit=5)
            found = [item for item in latest if item.get("source") == "devlot" and item.get("event") == "command:reset_workspace"]
            self.assertTrue(found)
            self.assertFalse(found[0].get("data", {}).get("ok", True))


if __name__ == "__main__":
    unittest.main()
