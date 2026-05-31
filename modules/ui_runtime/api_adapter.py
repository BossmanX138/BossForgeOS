from __future__ import annotations

from pathlib import Path
from typing import Any


def pin_state(process_obj: Any, view: str, alpha: float, is_running_fn) -> dict[str, Any]:
    if process_obj is not None and process_obj.poll() is not None:
        process_obj = None
        view = ""
    return {"ok": True, "running": bool(is_running_fn()), "view": view, "alpha": alpha, "_process": process_obj, "_view": view}


def pin_launch_payload(payload: dict[str, Any], current_alpha: float) -> tuple[str, float]:
    view = str(payload.get("view", "")).strip() or "view_status"
    try:
        alpha = float(payload.get("alpha", current_alpha))
    except (TypeError, ValueError):
        alpha = current_alpha
    alpha = max(0.35, min(1.0, alpha))
    return view, alpha


def pin_overlay_path(control_hall_file: str) -> Path:
    return Path(control_hall_file).resolve().parent / "pin_overlay.py"
