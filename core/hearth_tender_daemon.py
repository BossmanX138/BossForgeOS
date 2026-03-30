import argparse
import os
import shutil
import subprocess
import time
import threading
from typing import Any, Dict

from core.rune_bus import RuneBus, resolve_root_from_env
from modules.os_snapshot import snapshot_all


def safe_run(cmd: list[str]) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        return True, out.strip()
    except Exception as ex:
        return False, str(ex)


class HearthTender:
    def __init__(self, interval_seconds: int = 30, warn_threshold: float = 80.0) -> None:
        self.interval_seconds = interval_seconds
        self.warn_threshold = warn_threshold
        self.bus = RuneBus(resolve_root_from_env())
        self.seen_commands: set[str] = set()

    def docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def light_prune(self) -> Dict[str, Any]:
        if not self.docker_available():
            return {"ok": False, "message": "docker not available"}
        ok, out = safe_run(["docker", "container", "prune", "-f"])
        return {"ok": ok, "output": out}

    def full_prune(self) -> Dict[str, Any]:
        if not self.docker_available():
            return {"ok": False, "message": "docker not available"}
        ok, out = safe_run(["docker", "system", "prune", "-f"])
        return {"ok": ok, "output": out}

    def compact_vhdx(self) -> Dict[str, Any]:
        # This keeps behavior safe by using the bus pattern first.
        return {
            "ok": False,
            "message": "compact_vhdx requested; manual admin flow required on Windows",
        }

    def handle_command(self, payload: Dict[str, Any]) -> None:
        if payload.get("target") not in {"hearth", "hearth_tender"}:
            return

        command = payload.get("command")
        if command == "light_prune":
            result = self.light_prune()
        elif command == "full_prune":
            result = self.full_prune()
        elif command == "compact_vhdx":
            result = self.compact_vhdx()
        elif command == "status_ping":
            result = {"ok": True, "status": "alive"}
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("hearth_tender", f"command:{command}", result)

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            snapshot = snapshot_all()
            self.bus.write_state("hearth_tender", {"service": "hearth_tender", "pid": os.getpid(), **snapshot})

            disk_percent = snapshot["disk"]["percent"]
            if disk_percent >= self.warn_threshold:
                self.bus.emit_event(
                    "hearth_tender",
                    "disk_warning",
                    {"percent": disk_percent, "threshold": self.warn_threshold},
                    level="warning",
                )

            for _, cmd_payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(cmd_payload)

            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Hearth Tender daemon")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--warn-threshold", type=float, default=80.0)
    args = parser.parse_args()

    daemon = HearthTender(interval_seconds=args.interval, warn_threshold=args.warn_threshold)
    daemon.run_forever()


if __name__ == "__main__":
    main()
