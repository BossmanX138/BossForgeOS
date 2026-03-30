import argparse
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.rune_bus import RuneBus, resolve_root_from_env


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
        self.last_metrics: dict[str, Any] = {}
        self._ensure_profile()

    def _ensure_profile(self) -> None:
        if not self.profile_path.exists():
            self.profile_path.write_text(__import__("json").dumps(TEST_SENTINEL_PROFILE, indent=2), encoding="utf-8")

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
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("test_sentinel", f"command:{command}", result)
        self.bus.write_state(
            "test_sentinel",
            {
                "service": "test_sentinel",
                "pid": os.getpid(),
                "last_command": command,
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
                    "last_metrics_at": self.last_metrics.get("timestamp", ""),
                },
            )
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
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
