from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def get_voice_status(bus: Any) -> dict[str, Any]:
    pending_path = bus.state / "runeforge_pending_approval.json"
    runeforge_state_path = bus.state / "runeforge.json"

    pending = _safe_read_json(pending_path)
    if pending is None and pending_path.exists():
        pending = {"error": "invalid pending approval state"}

    last_report = None
    state = _safe_read_json(runeforge_state_path)
    if isinstance(state, dict):
        if isinstance(state.get("report"), dict):
            last_report = state.get("report")
        elif isinstance(state.get("execution"), dict) and isinstance(state.get("execution", {}).get("report"), dict):
            last_report = state.get("execution", {}).get("report")

    if last_report is None:
        events = bus.read_latest_events(limit=120)
        for item in events:
            if str(item.get("source", "")).strip() != "runeforge":
                continue
            event_name = str(item.get("event", "")).strip()
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            if event_name in {"sentinel_plan_approval_result", "sentinel_recommendations_applied", "os_action_approval_result"}:
                if isinstance(data.get("report"), dict):
                    last_report = data.get("report")
                elif isinstance(data.get("execution"), dict) and isinstance(data.get("execution", {}).get("report"), dict):
                    last_report = data.get("execution", {}).get("report")
                else:
                    last_report = {
                        "action_type": event_name,
                        "ok": bool(data.get("ok", True)),
                    }
                break

    return {"ok": True, "pending_approval": pending, "last_report": last_report}

