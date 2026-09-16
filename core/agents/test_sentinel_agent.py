import argparse
import json
import os
import sys
import pathlib

# === Path Resolver for Bundled/Source Modes ===
def get_project_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parent.parent.parent

PROJECT_ROOT = get_project_root()
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.rune.rune_bus import RuneBus, resolve_root_from_env

from core.agent_registry import register_agent


TEST_SENTINEL_PROFILE: dict[str, Any] = {
    "id": "test_sentinel",
    "name": "Test Sentinel",
    "version": "1.0.0",
    "description": "Tracks test debt and test metrics for BossForge projects.",
}


class TestSentinelAgent:
    def __init__(self, interval_seconds: int = 45, root: Path | None = None) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(root or resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.profile_path = self.bus.state / "test_sentinel_profile.json"
        self.tasks_path = self.bus.state / "test_sentinel_tasks.json"
        self.last_metrics: dict[str, Any] = {}
        self.work_items: list[dict[str, Any]] = []
        self._ensure_profile()
        self._load_work_items()
        
        # Register with central agent registry
        profile = {
            "id": "test_sentinel",
            "name": "TestSentinelAgent",
            "description": "Tracks test debt and test metrics for BossForge projects.",
        }
        register_agent("test_sentinel", profile)

    def _ensure_profile(self) -> None:
        if not self.profile_path.exists():
            self.profile_path.write_text(json.dumps(TEST_SENTINEL_PROFILE, indent=2), encoding="utf-8")

    def _load_work_items(self) -> None:
        if not self.tasks_path.exists():
            return
        try:
            payload = json.loads(self.tasks_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if isinstance(items, list):
            self.work_items = [item for item in items if isinstance(item, dict)]

    def _save_work_items(self) -> None:
        self.tasks_path.write_text(json.dumps({"items": self.work_items}, indent=2), encoding="utf-8")

    def add_work_item(self, args: dict[str, Any]) -> dict[str, Any]:
        delegated_handoff = bool(args.get("delegated_handoff", False))
        item = {
            "packet_id": str(args.get("packet_id", "")).strip(),
            "title": str(args.get("title", "")).strip(),
            "details": str(args.get("details", "")).strip(),
            "owner": "test_sentinel",
            "status": "in_progress" if delegated_handoff else "queued",
            "source": str(args.get("source", "")).strip(),
            "source_path": str(args.get("source_path", "")).strip(),
            "source_line": int(args.get("source_line", 0) or 0),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": datetime.now(timezone.utc).isoformat() if delegated_handoff else "",
        }
        self.work_items.append(item)
        self._save_work_items()
        return {"ok": True, "work_item": item, "queued_total": len(self.work_items)}

    def _submit_regression_to_runeforge(self, item: dict[str, Any], suite_result: dict[str, Any]) -> None:
        msg = str(suite_result.get("message", "verification failed")).strip()
        stderr = str(suite_result.get("stderr", "")).strip()[:500]
        detail = (msg + ("; " + stderr if stderr else "")).strip() or "post-fix verification failed"
        payload = {
            "project_path": str(self.bus.root),
            "source_doc": str(item.get("source_path", "") or "test_suite"),
            "submitted_by": "test_sentinel",
            "items": [
                {
                    "id": f"regression-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                    "title": str(item.get("title", "test regression"))[:140],
                    "details": detail,
                    "assignee": "codemage",
                    "severity": "high",
                    "source_path": str(item.get("source_path", "")),
                    "source_line": int(item.get("source_line", 0) or 0),
                    "suggested_next_action": "Fix test regression and re-run suite",
                    "is_test_debt": True,
                }
            ],
        }
        self.bus.emit_command("runeforge", "review_archivist_delegations", payload, issued_by="test_sentinel")
        self.bus.emit_event(
            "test_sentinel",
            "post_fix_regression_detected",
            {
                "title": str(item.get("title", "")),
                "rerouted_to": "runeforge",
                "returncode": suite_result.get("returncode"),
            },
        )

    def _process_delegated_handoffs(self) -> dict[str, Any]:
        changed = False
        completed = 0
        blocked = 0
        for item in self.work_items:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("delegated_handoff", False)):
                continue
            if str(item.get("status", "")).strip().lower() != "in_progress":
                continue
            if bool(item.get("post_fix_checked", False)):
                continue

            suite = self._run_test_suite(timeout_seconds=180)
            item["post_fix_checked"] = True
            item["post_fix_verified_at"] = datetime.now(timezone.utc).isoformat()
            if bool(suite.get("ok", False)):
                item["status"] = "completed"
                item["completed_by"] = "test_sentinel"
                item["completed_at"] = datetime.now(timezone.utc).isoformat()
                item["resolution"] = "Delegated test item verified by test suite"
                completed += 1
            else:
                item["status"] = "blocked"
                item["post_fix_issues"] = [str(suite.get("message", "verification failed"))]
                self._submit_regression_to_runeforge(item, suite)
                blocked += 1
            changed = True

        if changed:
            self._save_work_items()
        if completed:
            self.bus.emit_event("test_sentinel", "work_item_completed", {"ok": True, "completed_count": completed, "post_fix_verified": True})
        return {"changed": changed, "completed": completed, "blocked": blocked}

    def _workspace_tests_root(self) -> Path:
        return self.bus.root / "tests"

    def _scan_test_debt(self) -> dict[str, Any]:
        tests_root = self._workspace_tests_root()
        if not tests_root.exists() or not tests_root.is_dir():
            return {
                "ok": True,
                "tests_root": str(tests_root),
                "files_scanned": 0,
                "test_debt_hits": 0,
                "items": [],
                "message": "tests directory not found",
            }

        pattern = re.compile(r"TODO|FIXME|TBD", re.IGNORECASE)
        files_scanned = 0
        items: list[dict[str, Any]] = []

        for path in tests_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".txt"}:
                continue
            files_scanned += 1
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, start=1):
                if pattern.search(line):
                    items.append(
                        {
                            "file": str(path),
                            "line": idx,
                            "text": line.strip()[:240],
                            "severity": "high" if "fixme" in line.lower() else "medium",
                        }
                    )

        return {
            "ok": True,
            "tests_root": str(tests_root),
            "files_scanned": files_scanned,
            "test_debt_hits": len(items),
            "items": items[:200],
        }

    def _run_test_suite(self, timeout_seconds: int = 300) -> dict[str, Any]:
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.bus.root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "message": "test suite timed out",
                "timeout_seconds": timeout_seconds,
                "command": cmd,
            }
        except Exception as ex:
            return {"ok": False, "message": str(ex), "command": cmd}

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        merged = "\n".join([stdout, stderr]).strip()

        ran_match = re.search(r"Ran\s+(\d+)\s+tests?", merged)
        tests_ran = int(ran_match.group(1)) if ran_match else 0
        failed = "FAILED" in merged
        passed = ("OK" in merged) and not failed

        return {
            "ok": proc.returncode == 0,
            "command": cmd,
            "returncode": proc.returncode,
            "tests_ran": tests_ran,
            "passed": passed,
            "failed": failed,
            "stdout": stdout,
            "stderr": stderr,
        }

    def collect_metrics(self) -> dict[str, Any]:
        debt = self._scan_test_debt()
        suite = self._run_test_suite(timeout_seconds=300)
        metrics = {
            "ok": bool(debt.get("ok")) and bool(suite.get("ok")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_debt": debt,
            "test_suite": suite,
        }
        self.last_metrics = metrics
        return metrics

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "test_sentinel":
            return

        command = str(payload.get("command", "")).strip()
        if command == "status_ping":
            result = {
                "ok": True,
                "status": "alive",
                "last_metrics_at": self.last_metrics.get("timestamp", ""),
                "test_debt_hits": (
                    self.last_metrics.get("test_debt", {}).get("test_debt_hits", 0)
                    if isinstance(self.last_metrics.get("test_debt", {}), dict)
                    else 0
                ),
            }
        elif command in {"scan_test_debt", "collect_test_metrics", "run_test_metrics"}:
            result = self.collect_metrics()
        elif command == "run_test_suite":
            result = self._run_test_suite(timeout_seconds=300)
        elif command == "work_item":
            result = self.add_work_item(payload.get("args") if isinstance(payload.get("args"), dict) else {})
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("test_sentinel", f"command:{command}", result)
        self.bus.write_state(
            "test_sentinel",
            {
                "service": "test_sentinel",
                "pid": os.getpid(),
                "last_command": command,
                "queued_work_items": len(self.work_items),
                **result,
            },
        )

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "test_sentinel",
                {
                    "service": "test_sentinel",
                    "pid": os.getpid(),
                    "status": "idle",
                    "queued_work_items": len(self.work_items),
                    "last_metrics_at": self.last_metrics.get("timestamp", ""),
                },
            )
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
            self._process_delegated_handoffs()
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Test Sentinel agent")
    parser.add_argument("--interval", type=int, default=45)
    args = parser.parse_args()

    agent = TestSentinelAgent(interval_seconds=args.interval)
    agent.run_forever()


if __name__ == "__main__":
    main()
