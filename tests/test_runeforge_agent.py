import tempfile
import unittest
from pathlib import Path

from core.agents.runeforge_agent import RuneforgeAgent


class RuneforgeAgentTests(unittest.TestCase):
    def test_status_ping_emits_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = RuneforgeAgent(root=root)
            agent.handle_command({"target": "runeforge", "command": "status_ping", "args": {}})

            latest = agent.bus.read_latest_events(limit=5)
            self.assertTrue(any(item.get("source") == "runeforge" and item.get("event") == "command:status_ping" for item in latest))

    def test_work_item_is_queued(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = RuneforgeAgent(root=root)
            agent.handle_command(
                {
                    "target": "runeforge",
                    "command": "work_item",
                    "args": {"packet_id": "P0.1", "title": "task-1", "details": "set up runtime"},
                }
            )

            result = agent.list_tasks()
            self.assertTrue(result.get("ok"))
            tasks = result.get("tasks", [])
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].get("owner"), "runeforge")


if __name__ == "__main__":
    unittest.main()
