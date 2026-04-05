import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuneBus:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or Path.home() / "BossCrafts")
        self.bus = self.root / "bus"
        self.events = self.bus / "events"
        self.commands = self.bus / "commands"
        self.state = self.bus / "state"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        self.events.mkdir(parents=True, exist_ok=True)
        self.commands.mkdir(parents=True, exist_ok=True)
        self.state.mkdir(parents=True, exist_ok=True)

    def _write_json(self, folder: Path, prefix: str, payload: Dict[str, Any]) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = folder / f"{prefix}_{stamp}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def emit_command(self, target: str, command: str, args: Optional[Dict[str, Any]] = None, issued_by: str = "cli") -> Path:
        payload = {
            "type": "command",
            "target": target,
            "command": command,
            "args": args or {},
            "issued_by": issued_by,
            "timestamp": _utc_now_iso(),
        }
        return self._write_json(self.commands, "cmd", payload)

    def emit_event(self, source: str, event: str, data: Optional[Dict[str, Any]] = None, level: str = "info") -> Path:
        payload = {
            "type": "event",
            "source": source,
            "event": event,
            "level": level,
            "data": data or {},
            "timestamp": _utc_now_iso(),
        }
        return self._write_json(self.events, "evt", payload)

    def write_state(self, name: str, payload: Dict[str, Any]) -> Path:
        path = self.state / f"{name}.json"
        payload = dict(payload)
        payload.setdefault("timestamp", _utc_now_iso())
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def read_latest_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for path in sorted(self.events.glob("*.json"), reverse=True)[:limit]:
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return items

    def poll_commands(self, seen: Optional[set[str]] = None) -> List[tuple[Path, Dict[str, Any]]]:
        known = seen if seen is not None else set()
        found: List[tuple[Path, Dict[str, Any]]] = []
        for path in sorted(self.commands.glob("*.json")):
            if path.name in known:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                known.add(path.name)
                continue
            known.add(path.name)
            found.append((path, payload))
        return found


def resolve_root_from_env() -> Path:
    env_root = os.environ.get("BOSSFORGE_ROOT")
    return Path(env_root).expanduser() if env_root else Path.home() / "BossCrafts"
