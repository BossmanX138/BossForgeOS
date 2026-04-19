import json
import tempfile
import unittest
from pathlib import Path

from core.rune.agent_trace import AgentTrace


class AgentTraceTests(unittest.TestCase):
    def test_record_creates_trace_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("archivist", Path(tmp))
            path = trace.record("status_ping", {"x": 1}, {"ok": True}, duration_ms=12.5, issued_by="test")
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["agent_id"], "archivist")
            self.assertEqual(data["command"], "status_ping")
            self.assertEqual(data["args"], {"x": 1})
            self.assertEqual(data["result"], {"ok": True})
            self.assertAlmostEqual(data["duration_ms"], 12.5)
            self.assertEqual(data["issued_by"], "test")
            self.assertIn("timestamp", data)

    def test_record_without_duration_omits_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("runeforge", Path(tmp))
            path = trace.record("work_item")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("duration_ms", data)

    def test_record_defaults_args_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("devlot", Path(tmp))
            path = trace.record("reset")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["args"], {})
            self.assertEqual(data["result"], {})

    def test_traces_dir_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("codemage", Path(tmp))
            self.assertTrue(trace.traces_dir.exists())
            self.assertTrue(trace.traces_dir.is_dir())

    def test_read_recent_returns_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("devlot", Path(tmp))
            trace.record("cmd_a", {}, {})
            trace.record("cmd_b", {}, {})
            trace.record("cmd_c", {}, {})
            records = trace.read_recent(limit=3)
            self.assertEqual(len(records), 3)
            commands = [r["command"] for r in records]
            # Newest first: cmd_c was written last
            self.assertEqual(commands[0], "cmd_c")

    def test_read_recent_respects_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("devlot", Path(tmp))
            for i in range(5):
                trace.record(f"cmd_{i}")
            records = trace.read_recent(limit=2)
            self.assertEqual(len(records), 2)

    def test_empty_traces_dir_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("codemage", Path(tmp))
            self.assertEqual(trace.read_recent(), [])

    def test_agent_id_is_normalised_to_lowercase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTrace("RuneForge", Path(tmp))
            self.assertEqual(trace.agent_id, "runeforge")

    def test_multiple_agents_have_separate_trace_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            t1 = AgentTrace("archivist", root)
            t2 = AgentTrace("devlot", root)
            t1.record("cmd_a")
            t2.record("cmd_b")
            self.assertEqual(len(t1.read_recent()), 1)
            self.assertEqual(len(t2.read_recent()), 1)
            self.assertNotEqual(t1.traces_dir, t2.traces_dir)


if __name__ == "__main__":
    unittest.main()
