from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_TASK_STATUSES = {"assigned", "in_progress", "blocked", "done"}


def slugify(value: str) -> str:
    safe = re.sub(r"[^a-z0-9_-]+", "_", str(value).strip().lower())
    return safe.strip("_") or "task"


def extract_assigned_tasks(assignments_path: Path) -> list[dict[str, Any]]:
    if not assignments_path.exists():
        return []

    try:
        lines = assignments_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    items: list[dict[str, Any]] = []
    count_by_agent: dict[str, int] = {}
    now = datetime.now(timezone.utc).isoformat()

    for raw in lines:
        line = raw.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        body = line[2:].strip()
        agent_part, task_part = body.split(":", 1)
        agent = agent_part.strip()
        task = task_part.strip()
        if not agent or not task:
            continue

        agent_key = slugify(agent)
        count_by_agent[agent_key] = count_by_agent.get(agent_key, 0) + 1
        task_id = f"{agent_key}-{count_by_agent[agent_key]}"
        items.append(
            {
                "id": task_id,
                "agent": agent,
                "task": task,
                "status": "assigned",
                "started_at": "",
                "completed_at": "",
                "updated_at": now,
                "note": "",
            }
        )
    return items


def default_agent_task_state(assignments_path: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {"ok": True, "updated_at": now, "items": extract_assigned_tasks(assignments_path)}


def normalize_agent_task_state(state: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    items = state.get("items") if isinstance(state.get("items"), list) else []
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "assigned")).strip().lower()
        if status not in VALID_TASK_STATUSES:
            status = "assigned"
        normalized_items.append(
            {
                "id": str(item.get("id", "")).strip(),
                "agent": str(item.get("agent", "unknown-agent")).strip() or "unknown-agent",
                "task": str(item.get("task", "")).strip(),
                "status": status,
                "started_at": str(item.get("started_at", "")).strip(),
                "completed_at": str(item.get("completed_at", "")).strip(),
                "updated_at": str(item.get("updated_at", "")).strip() or now,
                "note": str(item.get("note", "")).strip(),
            }
        )
    return {"ok": True, "updated_at": str(state.get("updated_at", "")).strip() or now, "items": normalized_items}


def update_task_status(task: dict[str, Any], status: str, note: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    task["status"] = status
    task["updated_at"] = now
    if status == "in_progress" and not str(task.get("started_at", "")).strip():
        task["started_at"] = now
    if status == "done":
        if not str(task.get("started_at", "")).strip():
            task["started_at"] = now
        task["completed_at"] = now
    elif status in {"assigned", "in_progress", "blocked"}:
        if status != "blocked":
            task["completed_at"] = ""
    if note:
        task["note"] = note
