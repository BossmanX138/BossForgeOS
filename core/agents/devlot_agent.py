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
import threading
import time
from pathlib import Path
from typing import Any

from core.rune.rune_bus import RuneBus, resolve_root_from_env

from core.agent_registry import register_agent

# HuggingFaceConnector import
from core.connectors.huggingface_connector import HuggingFaceConnector


DEVLOT_PROFILE: dict[str, Any] = {
    "id": "devlot",
    "name": "Devlot, Machine-Smith of the Forge",
    "version": "1.0.0",
    "description": "Environment steward and execution utility agent for BossForge tasks.",
}


class DevlotAgent:
    def __init__(self, interval_seconds: int = 10, root: Path | None = None) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(root or resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.profile_path = self.bus.state / "devlot_profile.json"
        self.tasks_path = self.bus.state / "devlot_tasks.json"
        self.work_packets: list[dict[str, Any]] = []
        self._ensure_profile()
        self._load_tasks()
        
        # Register with central agent registry
        profile = {
            "id": "devlot",
            "name": "DevlotAgent",
            "description": "Environment steward and execution utility agent for BossForge tasks.",
        }
        register_agent("devlot", profile)

        # HuggingFaceConnector instance (token from env)
        try:
            self.hf = HuggingFaceConnector()
        except Exception as ex:
            self.hf = None
            self.bus.emit_event(
                "devlot", "huggingface_connector_init_failed", {"ok": False, "error": str(ex)}
            )

    def _ensure_profile(self) -> None:
        if self.profile_path.exists():
            return
        self.profile_path.write_text(json.dumps(DEVLOT_PROFILE, indent=2), encoding="utf-8")

    def _load_tasks(self) -> None:
        if not self.tasks_path.exists():
            return
        try:
            payload = json.loads(self.tasks_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if isinstance(items, list):
            self.work_packets = [item for item in items if isinstance(item, dict)]

    def _save_tasks(self) -> None:
        self.tasks_path.write_text(json.dumps({"items": self.work_packets}, indent=2), encoding="utf-8")

    def add_work_packet(self, args: dict[str, Any]) -> dict[str, Any]:
        packet = {
            "id": str(args.get("id", "")).strip() or f"packet_{len(self.work_packets) + 1}",
            "objective": str(args.get("objective", "")).strip(),
            "deliverables": args.get("deliverables") if isinstance(args.get("deliverables"), list) else [],
            "status": "queued",
        }
        self.work_packets.append(packet)
        self._save_tasks()
        return {"ok": True, "work_packet": packet, "queued_total": len(self.work_packets)}

    def add_work_item(self, args: dict[str, Any]) -> dict[str, Any]:
        item = {
            "packet_id": str(args.get("packet_id", "")).strip(),
            "title": str(args.get("title", "")).strip(),
            "details": str(args.get("details", "")).strip(),
            "owner": "devlot",
            "status": "queued",
        }
        self.work_packets.append(item)
        self._save_tasks()
        return {"ok": True, "work_item": item, "queued_total": len(self.work_packets)}

    def list_tasks(self) -> dict[str, Any]:
        return {"ok": True, "tasks": self.work_packets}

    def reset_workspace(self, args: dict[str, Any]) -> dict[str, Any]:
        # Safe by default: refuse destructive behavior unless explicit confirmation is supplied.
        confirmed = bool(args.get("confirm", False))
        if not confirmed:
            return {
                "ok": False,
                "message": "reset_workspace requires confirm=true; no changes made",
            }
        return {
            "ok": True,
            "message": "reset_workspace acknowledged; apply explicit task script for concrete actions",
        }

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "devlot":
            return

        command = str(payload.get("command", ""))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}


        # === Hugging Face Connector Commands ===
        if command == "hf_search_models":
            if not self.hf:
                result = {"ok": False, "error": "HuggingFaceConnector not initialized"}
            else:
                query = args.get("query", "")
                limit = int(args.get("limit", 10))
                result = self.hf.search_models(query, limit)
            self.bus.emit_event("devlot", "hf_search_models", result)
        elif command == "hf_list_models":
            if not self.hf:
                result = {"ok": False, "error": "HuggingFaceConnector not initialized"}
            else:
                author = args.get("author", None)
                limit = int(args.get("limit", 10))
                result = self.hf.list_models(author, limit)
            self.bus.emit_event("devlot", "hf_list_models", result)
        elif command == "hf_download_model":
            if not self.hf:
                result = {"ok": False, "error": "HuggingFaceConnector not initialized"}
            else:
                repo_id = args.get("repo_id", "")
                filename = args.get("filename", "")
                dest_path = args.get("dest_path", "")
                result = self.hf.download_model(repo_id, filename, dest_path)
            self.bus.emit_event("devlot", "hf_download_model", result)
        # === End Hugging Face Connector Commands ===
        elif command == "status_ping":
            result = {"ok": True, "status": "alive", "queued_work_packets": len(self.work_packets)}
        elif command == "work_packet":
            result = self.add_work_packet(args)
        elif command == "work_item":
            result = self.add_work_item(args)
        elif command == "list_tasks":
            result = self.list_tasks()
        elif command == "reset_workspace":
            result = self.reset_workspace(args)
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("devlot", f"command:{command}", result)
        self.bus.write_state(
            "devlot",
            {
                "service": "devlot",
                "pid": os.getpid(),
                "last_command": command,
                "queued_work_packets": len(self.work_packets),
                **result,
            },
        )

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "devlot",
                {
                    "service": "devlot",
                    "pid": os.getpid(),
                    "status": "idle",
                    "queued_work_packets": len(self.work_packets),
                },
            )
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Devlot agent")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    agent = DevlotAgent(interval_seconds=args.interval)
    agent.run_forever()


if __name__ == "__main__":
    main()
