import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.agents.archivist_agent import ArchivistAgent
from core.rune.rune_bus import RuneBus


class ArchivistAgentTests(unittest.TestCase):
    def test_archive_logs_copies_bus_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = RuneBus(root)
            bus.emit_event("hearth_tender", "disk_warning", {"percent": 91})
            bus.emit_command("archivist", "status_ping", {})

            agent = ArchivistAgent(root=root)
            result = agent.archive_logs()

            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["events_archived"], 1)
            self.assertGreaterEqual(result["commands_archived"], 1)

    def test_summarize_events_writes_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = RuneBus(root)
            bus.emit_event("hearth_tender", "disk_warning", {"percent": 91}, level="warning")
            bus.emit_event("archivist", "command:archive_logs", {"ok": True})

            agent = ArchivistAgent(root=root)
            result = agent.summarize_events(limit=20)

            self.assertTrue(result["ok"])
            self.assertIn("summary_path", result)
            summary_path = Path(result["summary_path"])
            self.assertTrue(summary_path.exists())

            data = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn("by_source", data)
            self.assertIn("hearth_tender", data["by_source"])

    def test_snapshot_state_copies_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = RuneBus(root)
            bus.write_state("hearth_tender", {"service": "hearth_tender", "status": "ok"})

            agent = ArchivistAgent(root=root)
            result = agent.snapshot_state()

            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["files_copied"], 1)

    def test_on_invoke_creates_governance_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_a"
            project.mkdir()

            agent = ArchivistAgent(root=root)
            add_result = agent.add_onboarded_project(str(project))
            self.assertTrue(add_result["ok"])

            result = agent.on_invoke()
            self.assertTrue(result["ok"])

            self.assertTrue((project / "docs" / "CHANGELOG.md").exists())
            self.assertTrue((project / "docs" / "decisions.md").exists())
            self.assertTrue((project / "docs" / "todos.md").exists())
            self.assertTrue((project / "docs" / "archivistREADME.md").exists())
            self.assertTrue((project / "docs" / "daily_ledger.md").exists())

    def test_add_onboarded_project_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_b"
            project.mkdir()

            agent = ArchivistAgent(root=root)
            add_result = agent.add_onboarded_project(str(project))

            self.assertTrue(add_result["ok"])
            self.assertTrue(agent.onboarded_projects_path.exists())

    def test_seal_queue_preview_and_reject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_d"
            project.mkdir()

            agent = ArchivistAgent(root=root)
            self.assertTrue(agent.add_onboarded_project(str(project))["ok"])
            invoke_result = agent.on_invoke()
            self.assertTrue(invoke_result["ok"])

            preview = agent.preview_seal()
            self.assertTrue(preview["ok"])
            before_count = len(preview.get("pending", []))
            self.assertGreaterEqual(before_count, 1)

            seal_id = preview["pending"][-1]["seal_id"]
            rejected = agent.reject_seal(seal_id=seal_id, reason="test")
            self.assertTrue(rejected["ok"])

            preview_after = agent.preview_seal()
            self.assertTrue(preview_after["ok"])
            self.assertEqual(len(preview_after.get("pending", [])), before_count - 1)

    def test_Archive_index_db_writes_sqlite_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_c"
            project.mkdir()
            (project / "README.md").write_text("# test\n", encoding="utf-8")
            (project / "notes.txt").write_text("todo\n", encoding="utf-8")

            db_path = root / "archives" / "index.sqlite3"
            agent = ArchivistAgent(root=root)
            result = agent.Archive_index_db(str(project), str(db_path), include_patterns=["*.md", "*.txt"])

            self.assertTrue(result["ok"])
            self.assertEqual(result["db_type"], "sqlite")
            self.assertGreaterEqual(result["rows_written"], 2)

            con = sqlite3.connect(str(db_path))
            try:
                count = con.execute("SELECT COUNT(*) FROM archivist_file_index").fetchone()[0]
            finally:
                con.close()

            self.assertGreaterEqual(count, 2)

    def test_approve_seal_non_git_moves_to_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_non_git"
            project.mkdir()

            agent = ArchivistAgent(root=root)
            self.assertTrue(agent.add_onboarded_project(str(project))["ok"])
            self.assertTrue(agent.on_invoke()["ok"])

            preview_before = agent.preview_seal()
            self.assertTrue(preview_before["ok"])
            before_pending = len(preview_before.get("pending", []))
            seal_id = preview_before["pending"][-1]["seal_id"]

            with patch.object(agent, "_is_git_repo", return_value=False):
                approved = agent.approve_seal(seal_id=seal_id, init_repo_if_missing=False)
            self.assertTrue(approved["ok"])
            self.assertEqual(approved["status"], "sealed_no_git")

            preview_after = agent.preview_seal()
            self.assertEqual(len(preview_after.get("pending", [])), before_pending - 1)
            history = preview_after.get("history", [])
            self.assertTrue(any(item.get("seal_id") == seal_id and item.get("status") == "sealed_no_git" for item in history))

    def test_approve_seal_push_uses_github_token_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_push"
            project.mkdir()

            agent = ArchivistAgent(root=root)
            self.assertTrue(agent.add_onboarded_project(str(project))["ok"])
            self.assertTrue(agent.on_invoke()["ok"])

            preview = agent.preview_seal()
            seal_id = preview["pending"][-1]["seal_id"]

            seen_commands: list[list[str]] = []

            def fake_git_run(_project: Path, args: list[str]) -> tuple[bool, str]:
                seen_commands.append(args)
                if args and args[0] == "add":
                    return True, ""
                if len(args) >= 6 and args[0] == "-c" and args[3] == "-c" and args[5] == "commit":
                    return True, "[main abc123] docs"
                if args == ["rev-parse", "HEAD"]:
                    return True, "abc123"
                if args[:2] == ["-c", "http.extraHeader=AUTHORIZATION: basic eC1hY2Nlc3MtdG9rZW46Z2hwX3Rlc3Q="] and args[-1] == "push":
                    return True, "pushed"
                return True, "ok"

            with patch.object(agent, "_is_git_repo", return_value=True), patch.object(
                agent, "_is_github_origin", return_value=True
            ), patch.object(agent, "_get_github_access_token", return_value="ghp_test"), patch.object(
                agent, "_git_run", side_effect=fake_git_run
            ):
                approved = agent.approve_seal(seal_id=seal_id, push=True)

            self.assertTrue(approved["ok"])
            push_calls = [cmd for cmd in seen_commands if cmd and cmd[-1] == "push"]
            self.assertEqual(len(push_calls), 1)
            self.assertTrue(any("http.extraHeader=AUTHORIZATION: basic" in part for part in push_calls[0]))

    def test_on_invoke_stewards_readme_toc_project_owned_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_docs"
            project.mkdir()
            (project / "README.md").write_text(
                "# Project Docs\n\nIntro text.\n\n## Quick Start\n\n- step\n\n## Notes\n\n- note\n",
                encoding="utf-8",
            )
            nested = project / "feature"
            nested.mkdir()
            (nested / "README.md").write_text(
                "# Feature\n\n## Usage\n\n- use\n",
                encoding="utf-8",
            )

            model_dir = project / ".models" / "third_party"
            model_dir.mkdir(parents=True)
            (model_dir / "README.md").write_text(
                "# Third Party\n\n## Keep\n\n- untouched\n",
                encoding="utf-8",
            )

            agent = ArchivistAgent(root=root)
            self.assertTrue(agent.add_onboarded_project(str(project))["ok"])
            self.assertTrue(agent.on_invoke()["ok"])

            root_readme = (project / "README.md").read_text(encoding="utf-8")
            self.assertIn("## Table of Contents", root_readme)
            self.assertIn("- [Quick Start](#quick-start)", root_readme)

            feature_readme = (nested / "README.md").read_text(encoding="utf-8")
            self.assertIn("## Table of Contents", feature_readme)
            self.assertIn("- [Usage](#usage)", feature_readme)

            third_party_readme = (model_dir / "README.md").read_text(encoding="utf-8")
            self.assertNotIn("## Table of Contents", third_party_readme)

    def test_collect_todos_avoids_partial_token_false_positives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_tokens"
            project.mkdir()
            source = project / "sample.py"
            source.write_text(
                "x = 'todo_or_open'\n"
                "y = 'VariantTimeToDosDateTime'\n"
                "# TODO: real work item\n",
                encoding="utf-8",
            )

            agent = ArchivistAgent(root=root)
            todos = agent._collect_todos(project)
            self.assertEqual(len(todos), 1)
            self.assertIn("TODO: real work item", str(todos[0].get("text", "")))

    def test_policy_overrides_todo_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project_policy"
            project.mkdir()
            (project / "notes.txt").write_text("ACTIONITEM: complete checklist\n", encoding="utf-8")

            state_dir = root / "bus" / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "archivist_policy.json").write_text(
                json.dumps(
                    {
                        "todo_patterns": ["ACTIONITEM"],
                        "todo_scan_suffixes": [".txt"],
                    }
                ),
                encoding="utf-8",
            )

            agent = ArchivistAgent(root=root)
            todos = agent._collect_todos(project)
            self.assertEqual(len(todos), 1)
            self.assertIn("ACTIONITEM", str(todos[0].get("text", "")))


if __name__ == "__main__":
    unittest.main()
