from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.security.security_sentinel_agent import SecuritySentinelAgent


def read_security_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"ok": True, "status": "idle", "findings": []}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"ok": False, "message": "invalid security state", "findings": []}
    if not isinstance(payload, dict):
        payload = {"ok": False, "message": "invalid security state", "findings": []}
    payload.setdefault("findings", [])
    return payload


def scan_workspace(path: str) -> tuple[dict[str, Any], int]:
    agent = SecuritySentinelAgent(interval_seconds=20)
    result = agent.scan_workspace(str(path or "").strip())
    agent.bus.emit_event("security_sentinel", "manual:scan_workspace", result)
    agent.bus.write_state(
        "security_sentinel",
        {"service": "security_sentinel", "pid": os.getpid(), "last_command": "scan_workspace", **result},
    )
    status = 200 if result.get("ok") else 400
    return result, status


def list_secrets() -> dict[str, Any]:
    return SecuritySentinelAgent(interval_seconds=20).list_secrets()


def set_policy(agent_name: str, actions: list[str]) -> tuple[dict[str, Any], int]:
    result = SecuritySentinelAgent(interval_seconds=20).set_policy(str(agent_name or "").strip(), actions)
    status = 200 if result.get("ok") else 400
    return result, status


def check_policy(agent_name: str, action: str) -> dict[str, Any]:
    return SecuritySentinelAgent(interval_seconds=20).check_policy(str(agent_name or "").strip(), str(action or "").strip())
