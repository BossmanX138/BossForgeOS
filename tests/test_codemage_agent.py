import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch, Mock

from core.agents.codemage_agent import CodeMageAgent
from core.rune.rune_bus import RuneBus


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
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b'{"choices":[{"message":{"content":"1. Validate requirements\\n2. Implement changes\\n3. Run tests"}}],"usage":{"total_tokens":42}}'

            with patch("core.agents.codemage_agent.request.urlopen", return_value=_FakeResponse()):
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

    def test_process_pending_commands_skips_commands_consumed_before_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = RuneBus(root)
            historical = bus.emit_command("codemage", "status_ping")
            agent = CodeMageAgent(root=root)
            agent._save_command_cursor(historical.name)
            fresh = bus.emit_command("codemage", "list_work_packets")

            with patch.object(agent, "handle_command") as handle_command:
                agent._process_pending_commands()
            self.assertEqual(handle_command.call_count, 1)
            self.assertEqual(handle_command.call_args.args[0].get("command"), "list_work_packets")

            restarted = CodeMageAgent(root=root)
            with patch.object(restarted, "handle_command") as restarted_handle:
                restarted._process_pending_commands()
            restarted_handle.assert_not_called()
            self.assertEqual(json.loads(restarted.command_cursor_path.read_text(encoding="utf-8"))["last_command_file"], fresh.name)

    def test_generate_bossgate_patch_proposal_saves_allowlisted_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            (workspace / "docs").mkdir(parents=True)
            (workspace / "docs" / "bossgate_connector.md").write_text("# BossGate\n", encoding="utf-8")
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            diff = (
                "diff --git a/docs/bossgate_connector.md b/docs/bossgate_connector.md\n"
                "--- a/docs/bossgate_connector.md\n"
                "+++ b/docs/bossgate_connector.md\n"
                "@@ -1 +1,2 @@\n"
                " # BossGate\n"
                "+Chunked transfer proposal.\n"
            )
            with patch.object(agent, "_invoke_model", return_value={"ok": True, "text": diff, "model": "qwen"}):
                result = agent.generate_bossgate_patch_proposal({"todo_id": "BG-005", "details": "chunk transfers"})

            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("status"), "draft")
            proposal_path = Path(str(result.get("proposal_file")))
            self.assertTrue(proposal_path.exists())
            saved = json.loads(proposal_path.read_text(encoding="utf-8"))
            self.assertEqual(saved.get("todo_id"), "BG-005")
            self.assertIn("docs/bossgate_connector.md", saved.get("touched_files", []))

    def test_generate_bossgate_patch_proposal_rejects_outside_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            diff = (
                "diff --git a/core/agents/codemage_agent.py b/core/agents/codemage_agent.py\n"
                "--- a/core/agents/codemage_agent.py\n"
                "+++ b/core/agents/codemage_agent.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            )
            with patch.object(agent, "_invoke_model", return_value={"ok": True, "text": diff, "model": "qwen"}):
                result = agent.generate_bossgate_patch_proposal({"todo_id": "BG-005"})

            self.assertFalse(result.get("ok"))
            self.assertIn("outside BossGate proposal scope", str(result.get("message", "")))

    def test_generate_bossgate_patch_proposal_uses_requested_compact_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            (workspace / "docs").mkdir(parents=True)
            (workspace / "docs" / "bossgate_connector.md").write_text("# Connector\n" + ("x" * 100), encoding="utf-8")
            (workspace / "docs" / "bossgate_protocol.md").write_text("# Protocol\n" + ("y" * 100), encoding="utf-8")
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            diff = (
                "diff --git a/docs/bossgate_connector.md b/docs/bossgate_connector.md\n"
                "--- a/docs/bossgate_connector.md\n"
                "+++ b/docs/bossgate_connector.md\n"
                "@@ -1 +1,2 @@\n"
                " # Connector\n"
                "+Compact proposal.\n"
            )
            with patch("core.agents.codemage_agent.subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")):
                with patch.object(agent, "_invoke_model", return_value={"ok": True, "text": diff, "model": "qwen"}) as invoke:
                    result = agent.generate_bossgate_patch_proposal(
                        {
                            "todo_id": "BG-005",
                            "context_files": ["docs/bossgate_connector.md"],
                            "max_context_chars": 40,
                            "max_output_tokens": 96,
                        }
                    )

            self.assertTrue(result.get("ok"))
            prompt = str(invoke.call_args.kwargs.get("prompt", ""))
            self.assertIn("docs/bossgate_connector.md", prompt)
            self.assertNotIn("docs/bossgate_protocol.md", prompt)
            self.assertEqual(invoke.call_args.kwargs["request_overrides"]["max_tokens"], 96)

    def test_generate_bossgate_patch_proposal_uses_requested_line_range_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            (workspace / "docs").mkdir(parents=True)
            (workspace / "docs" / "bossgate_connector.md").write_text("line one\nline two\nline three\n", encoding="utf-8")
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            diff = (
                "diff --git a/docs/bossgate_connector.md b/docs/bossgate_connector.md\n"
                "--- a/docs/bossgate_connector.md\n"
                "+++ b/docs/bossgate_connector.md\n"
                "@@ -2 +2,2 @@\n"
                " line two\n"
                "+range proposal\n"
            )
            with patch("core.agents.codemage_agent.subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")):
                with patch.object(agent, "_invoke_model", return_value={"ok": True, "text": diff, "model": "qwen"}) as invoke:
                    result = agent.generate_bossgate_patch_proposal(
                        {
                            "todo_id": "BG-005",
                            "context_ranges": [{"file": "docs/bossgate_connector.md", "start_line": 2, "end_line": 2}],
                        }
                    )

            self.assertTrue(result.get("ok"))
            prompt = str(invoke.call_args.kwargs.get("prompt", ""))
            self.assertIn("docs/bossgate_connector.md lines 2-2", prompt)
            self.assertIn("line two", prompt)
            self.assertNotIn("line one", prompt)
            self.assertNotIn("line three", prompt)

    @patch("core.agents.codemage_agent.subprocess.run")
    def test_generate_bossgate_patch_proposal_rejects_diff_that_fails_git_preflight(self, mock_run: Mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            diff = (
                "diff --git a/docs/bossgate_connector.md b/docs/bossgate_connector.md\n"
                "--- a/docs/bossgate_connector.md\n"
                "+++ b/docs/bossgate_connector.md\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            )
            mock_run.return_value = Mock(returncode=128, stdout="", stderr="error: corrupt patch")
            with patch.object(agent, "_invoke_model", return_value={"ok": True, "text": diff, "model": "qwen"}):
                result = agent.generate_bossgate_patch_proposal({"todo_id": "BG-005"})

            self.assertFalse(result.get("ok"))
            self.assertIn("git apply --check", str(result.get("message", "")))
            self.assertEqual(list(agent.patch_proposals_dir.glob("*.json")), [])
            rejected = list(agent.patch_rejections_dir.glob("*.json"))
            self.assertEqual(len(rejected), 1)
            saved = json.loads(rejected[0].read_text(encoding="utf-8"))
            self.assertEqual(saved.get("status"), "rejected_preflight")
            self.assertIn("corrupt patch", str(saved.get("stderr", "")))

    @patch("core.agents.codemage_agent.subprocess.run")
    def test_generate_bossgate_patch_proposal_pins_single_context_path_and_strips_fence(self, mock_run: Mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            diff = (
                "diff --git a/docs/bosggate_connector.md b/docs/bosggate_connector.md\n"
                "--- a/docs/bosggate_connector.md\n"
                "+++ b/docs/bosggate_connector.md\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
                "```\n"
            )
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            with patch.object(agent, "_invoke_model", return_value={"ok": True, "text": diff, "model": "qwen"}):
                result = agent.generate_bossgate_patch_proposal(
                    {"todo_id": "BG-005", "context_files": ["docs/bossgate_connector.md"]}
                )

            self.assertTrue(result.get("ok"))
            saved = json.loads(Path(str(result.get("proposal_file"))).read_text(encoding="utf-8"))
            self.assertIn("a/docs/bossgate_connector.md b/docs/bossgate_connector.md", saved["patch"])
            self.assertNotIn("bosggate", saved["patch"])
            self.assertFalse(saved["patch"].rstrip().endswith("```"))

    def test_apply_bossgate_patch_proposal_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            proposal_id = "BG-005-test"
            proposal_path = agent.patch_proposals_dir / f"{proposal_id}.json"
            proposal_path.write_text(
                json.dumps({"proposal_id": proposal_id, "status": "draft", "patch": "diff --git a/docs/x b/docs/x\n"}),
                encoding="utf-8",
            )

            result = agent.apply_bossgate_patch_proposal({"proposal_id": proposal_id})

            self.assertFalse(result.get("ok"))
            self.assertIn("confirm=true", str(result.get("message", "")))

    @patch("core.agents.codemage_agent.subprocess.run")
    def test_apply_bossgate_patch_proposal_runs_check_apply_and_tests(self, mock_run: Mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            agent = CodeMageAgent(root=root, workspace_root=workspace)
            proposal_id = "BG-005-test"
            proposal_path = agent.patch_proposals_dir / f"{proposal_id}.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "proposal_id": proposal_id,
                        "status": "draft",
                        "patch": (
                            "diff --git a/docs/bossgate_connector.md b/docs/bossgate_connector.md\n"
                            "--- a/docs/bossgate_connector.md\n"
                            "+++ b/docs/bossgate_connector.md\n"
                        ),
                    }
                ),
                encoding="utf-8",
            )
            mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")

            result = agent.apply_bossgate_patch_proposal({"proposal_id": proposal_id, "confirm": True})

            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("status"), "verified")
            self.assertEqual(mock_run.call_count, 3)


if __name__ == "__main__":
    unittest.main()
