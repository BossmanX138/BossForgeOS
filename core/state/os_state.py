import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent_registry import list_all_agents
from core.rune.rune_bus import RuneBus, resolve_root_from_env


SCHEMA_VERSION = "bossforge.os-state.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _collect_state_tree(bus: RuneBus) -> dict[str, dict[str, Any]]:
    state_tree: dict[str, dict[str, Any]] = {}
    for path in sorted(bus.state.glob("*.json")):
        state_tree[path.stem] = _read_json_file(path)
    return state_tree


def _agent_runtime_summary(manifest: dict[str, dict[str, Any]], state_tree: dict[str, dict[str, Any]]) -> dict[str, Any]:
    runtime: dict[str, Any] = {}
    for agent_id, profile in manifest.items():
        state = state_tree.get(agent_id, {})
        status = str(state.get("status", "unknown")).strip().lower() or "unknown"
        runtime[agent_id] = {
            "id": agent_id,
            "name": profile.get("name", agent_id),
            "status": status,
            "last_seen": state.get("timestamp", ""),
            "state_present": bool(state),
        }
    return runtime


def build_os_state(root: Path | None = None, event_limit: int = 30) -> dict[str, Any]:
    bus = RuneBus(root or resolve_root_from_env())
    state_tree = _collect_state_tree(bus)
    manifest = list_all_agents()
    recent_events = bus.read_latest_events(limit=max(1, int(event_limit)))

    bus_files = {
        "state_files": bus.count_json_files(bus.state),
        "event_files": bus.count_json_files(bus.events),
        "command_files": bus.count_json_files(bus.commands),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "root": str(bus.root),
        "bus": bus_files,
        "agents": {
            "manifest": manifest,
            "runtime": _agent_runtime_summary(manifest, state_tree),
        },
        "state_tree": state_tree,
        "recent_events": recent_events,
    }


def diff_os_states(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    prev_tree = previous.get("state_tree") if isinstance(previous.get("state_tree"), dict) else {}
    curr_tree = current.get("state_tree") if isinstance(current.get("state_tree"), dict) else {}

    prev_keys = set(prev_tree.keys())
    curr_keys = set(curr_tree.keys())

    changed_keys: list[str] = []
    for key in sorted(prev_keys & curr_keys):
        if prev_tree.get(key) != curr_tree.get(key):
            changed_keys.append(key)

    prev_runtime = previous.get("agents", {}).get("runtime", {}) if isinstance(previous.get("agents"), dict) else {}
    curr_runtime = current.get("agents", {}).get("runtime", {}) if isinstance(current.get("agents"), dict) else {}

    status_changes: list[dict[str, str]] = []
    for agent_id in sorted(set(prev_runtime.keys()) & set(curr_runtime.keys())):
        prev_status = str((prev_runtime.get(agent_id) or {}).get("status", "unknown"))
        curr_status = str((curr_runtime.get(agent_id) or {}).get("status", "unknown"))
        if prev_status != curr_status:
            status_changes.append({"agent": agent_id, "from": prev_status, "to": curr_status})

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "added_state_keys": sorted(curr_keys - prev_keys),
        "removed_state_keys": sorted(prev_keys - curr_keys),
        "changed_state_keys": changed_keys,
        "agent_status_changes": status_changes,
    }