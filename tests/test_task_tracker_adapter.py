import tempfile
import unittest
from pathlib import Path

from modules.ops_runtime import task_tracker_adapter as tracker


class TaskTrackerAdapterTests(unittest.TestCase):
    def test_slugify_and_fallback(self) -> None:
        self.assertEqual(tracker.slugify("  Rune Forge Agent  "), "rune_forge_agent")
        self.assertEqual(tracker.slugify("***"), "task")

    def test_extract_assigned_tasks_parses_markdown_bullets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "AGENT_TASK_ASSIGNMENTS.md"
            p.write_text("\n".join([
                "- Agent One: Build tests",
                "- Agent One: Fix lint",
                "invalid line",
                "- : missing",
                "- Agent Two: Ship",
            ]), encoding="utf-8")

            items = tracker.extract_assigned_tasks(p)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["id"], "agent_one-1")
        self.assertEqual(items[1]["id"], "agent_one-2")
        self.assertEqual(items[2]["id"], "agent_two-1")
        self.assertTrue(all(x["status"] == "assigned" for x in items))

    def test_normalize_agent_task_state_sanitizes_items(self) -> None:
        state = {
            "updated_at": "",
            "items": [
                {"id": "1", "agent": "", "task": "x", "status": "weird", "note": 9},
                "skip-me",
            ],
        }
        normalized = tracker.normalize_agent_task_state(state)
        self.assertTrue(normalized["ok"])
        self.assertEqual(len(normalized["items"]), 1)
        self.assertEqual(normalized["items"][0]["status"], "assigned")
        self.assertEqual(normalized["items"][0]["agent"], "unknown-agent")
        self.assertEqual(normalized["items"][0]["note"], "9")

    def test_update_task_status_sets_start_and_complete_fields(self) -> None:
        task = {"status": "assigned", "started_at": "", "completed_at": "", "updated_at": "", "note": ""}
        tracker.update_task_status(task, "in_progress", "")
        self.assertEqual(task["status"], "in_progress")
        self.assertTrue(task["started_at"])
        self.assertEqual(task["completed_at"], "")

        tracker.update_task_status(task, "done", "done note")
        self.assertEqual(task["status"], "done")
        self.assertTrue(task["completed_at"])
        self.assertEqual(task["note"], "done note")


if __name__ == "__main__":
    unittest.main()
