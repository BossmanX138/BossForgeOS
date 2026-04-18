from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.rune.discovery_handoff import run_discovery_handoff, scheduled_discovery_window_key
from core.rune.rune_bus import RuneBus


def run_hourly_discovery_cycle(
    bus: RuneBus,
    agent_id: str,
    root: Path,
    last_window_key: str | None,
    window_minutes: int = 2,
) -> dict[str, Any]:
    window_key = scheduled_discovery_window_key(window_minutes=window_minutes)
    discovery_mode_active = bool(window_key)
    next_window_key = last_window_key

    if discovery_mode_active and window_key != last_window_key:
        sweep = run_discovery_handoff(
            bus,
            agent_id,
            {"scheduled_discovery": True, "scan_root": str(root)},
            root=root,
        )
        bus.emit_event(agent_id, "scheduled_discovery", sweep)
        next_window_key = window_key

    return {
        "discovery_mode_active": discovery_mode_active,
        "last_window_key": next_window_key,
    }


def auto_complete_discovery_items(
    bus: RuneBus,
    agent_id: str,
    items: list[dict[str, Any]],
    save_items: Callable[[], None],
) -> dict[str, Any]:
    completed: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    changed = False

    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).strip().lower() != "queued":
            continue
        is_discovery = bool(item.get("discovery_handoff", False)) or str(item.get("source", "")).strip().lower() == "discovery_mode"
        if not is_discovery:
            continue

        item["status"] = "completed"
        item["completed_by"] = agent_id
        item["completed_at"] = now_iso
        item["resolution"] = "Auto-processed discovery handoff TODO"
        completed.append(
            {
                "title": str(item.get("title", "")).strip(),
                "source_path": str(item.get("source_path", "")).strip(),
                "source_line": int(item.get("source_line", 0) or 0),
            }
        )
        changed = True

    if changed:
        save_items()

    summary = {
        "ok": True,
        "agent": agent_id,
        "completed_count": len(completed),
        "completed": completed[:20],
    }
    if completed:
        bus.emit_event(agent_id, "work_item_completed", summary)
        bus.emit_event(agent_id, "discovery_autocomplete", summary)
    return summary
