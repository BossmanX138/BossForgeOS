from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def default_state() -> dict[str, Any]:
    return {
        "steps": {
            "workspace_check": False,
            "security_baseline": False,
            "model_gateway": False,
        },
        "updated_at": "",
    }


def apply_step(
    state: dict[str, Any],
    step: str,
    project_root: Path,
    bus_root: Path,
) -> tuple[dict[str, Any], int]:
    key = str(step or "").strip().lower()
    if key == "workspace_check":
        checks = {
            "project_root_exists": project_root.exists(),
            "bus_state_exists": (bus_root / "state").exists(),
            "core_exists": (project_root / "core").exists(),
            "ui_exists": (project_root / "ui").exists(),
        }
        state.setdefault("checks", {}).update(checks)
        state.setdefault("steps", {})["workspace_check"] = all(bool(v) for v in checks.values())
    elif key in {"security_baseline", "model_gateway"}:
        state.setdefault("steps", {})[key] = True
    else:
        return {"ok": False, "message": "unsupported onboarding step"}, 400

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"ok": True, **state}, 200


def status_payload(state: dict[str, Any]) -> dict[str, Any]:
    steps = state.get("steps") if isinstance(state.get("steps"), dict) else {}
    completion = 0.0
    if steps:
        completion = round((sum(1 for value in steps.values() if bool(value)) / max(1, len(steps))) * 100.0, 1)
    return {"ok": True, "completion_percent": completion, **state}
