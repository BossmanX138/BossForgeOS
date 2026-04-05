import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from core.codemage_agent import CodeMageAgent
from core.rune_bus import RuneBus


class CodeMageAgentTests(unittest.TestCase):
    def test_status_ping_emits_event_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = CodeMageAgent(root=root)
            agent.handle_command({"target": "codemage", "command": "status_ping", "args": {}})

            latest = agent.bus.read_latest_events(limit=5)
            self.assertTrue(any(item.get("source") == "codemage" and item.get("event") == "command:status_ping" for item in latest))
            state = (RuneBus(root).state / "codemage.json").read_text(encoding="utf-8")
            self.assertIn('"service": "codemage"', state)

    def test_analyze_selection_handles_inline_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = CodeMageAgent(root=root)
            agent.handle_command(
                {
                    "target": "codemage",
                    "command": "analyze_selection",
                    "args": {"language": "python", "content": "print('x')\n# TODO: improve"},
                }
            )

            latest = agent.bus.read_latest_events(limit=5)
            found = [item for item in latest if item.get("source") == "codemage" and item.get("event") == "command:analyze_selection"]
            self.assertTrue(found)
            data = found[0].get("data", {})
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("language"), "python")
            self.assertGreaterEqual(data.get("line_count", 0), 1)

    def test_workspace_indexing_and_scroll_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            docs = project / "docs"
            docs.mkdir(parents=True)
            (docs / "plan.md").write_text(
                "# Ritual Plan\n\n1. Do this\n2. Do that\n\nTODO: fill missing step\nMUST keep tests passing\n",
                encoding="utf-8",
            )

            agent = CodeMageAgent(root=root)
            idx = agent.workspace_indexing({"path": str(project)})
            self.assertTrue(idx.get("ok"))
            self.assertTrue(any(item.endswith("plan.md") for item in idx.get("scrolls", [])))

            read = agent.scroll_reading({"scroll_path": str(docs / "plan.md")})
            self.assertTrue(read.get("ok"))
            self.assertGreaterEqual(len(read.get("explicit_steps", [])), 2)
            self.assertGreaterEqual(len(read.get("todo_or_open", [])), 1)
            self.assertGreaterEqual(len(read.get("constraints", [])), 1)

    def test_execute_work_packet_creates_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = CodeMageAgent(root=root)
            added = agent.add_work_packet({"id": "P0.1", "objective": "Build connector", "deliverables": ["module", "tests"]})
            self.assertTrue(added.get("ok"))

            class _FakeResponse:
                def R:\Making_Runeforge
                __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b'{"choices":[{"message":{"content":"1. Validate requirements\\n2. Implement changes\\n3. Run tests"}}],"usage":{"total_tokens":42}}'

            with patch("core.codemage_agent.request.urlopen", return_value=_FakeResponse()):
                out = agent.execute_work_packet({"id": "P0.1"})
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("id"), "P0.1")
            self.assertGreaterEqual(len(out.get("execution_plan", [])), 2)
            self.assertTrue(any("Model-core guidance:" in str(step) for step in out.get("execution_plan", [])))
            self.assertTrue(out.get("model", {}).get("ok"))
            delegated = out.get("delegated_items", [])
            self.assertGreaterEqual(len(delegated), 1)
            targets = {item.get("target") for item in delegated if isinstance(item, dict)}
            self.assertTrue({"devlot", "runeforge"}.intersection(targets))

            command_files = sorted((root / "bus" / "commands").glob("*.json"))
            self.assertTrue(command_files)
            command_payloads = [json.loads(path.read_text(encoding="utf-8")) for path in command_files]
            self.assertTrue(
                any(
                    payload.get("command") == "work_item" and payload.get("target") in {"devlot", "runeforge"}
                    for payload in command_payloads
                )
            )
            self.assertIn("The scroll is complete", str(out.get("message", "")))

    def test_set_model_backend_updates_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = CodeMageAgent(root=root)
            result = agent.set_model_backend(
                {
                    "endpoint": "vllm",
                    "provider": "openai_compatible",
                    "url": "http://127.0.0.1:8001/v1/chat/completions",
                    "model": "Qwen/Qwen2.5-3B-Instruct",
                    "timeout_seconds": 5,
                }
            )
            self.assertTrue(result.get("ok"))
            models = result.get("models", {})
            self.assertEqual(models.get("default_endpoint"), "vllm")
            inference = models.get("inference", {})
            self.assertEqual(inference.get("url"), "http://127.0.0.1:8001/v1/chat/completions")
            self.assertEqual(inference.get("model"), "Qwen/Qwen2.5-3B-Instruct")


if __name__ == "__main__":
    unittest.main()
