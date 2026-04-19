"""BossCrafts Protocol v1 versioning and compatibility checks.

Provides:
  - ``PROTOCOL_VERSION`` — the current protocol version string.
  - ``is_compatible(version_str)`` — check whether a message version is compatible.
  - ``validate_message(payload)`` — validate a raw dict against the v1 envelope schema.
  - ``wrap_event(...)`` — build a protocol-compliant event envelope.
  - ``wrap_command(...)`` — build a protocol-compliant command envelope.
  - ``load_schema()`` — load the raw JSON Schema file.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"

_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")
_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schemas" / "bosscrafts_protocol_v1.json"
_REQUIRED_FIELDS = frozenset({"protocol_version", "type", "timestamp"})
_VALID_TYPES = frozenset({"event", "command"})
_VALID_LEVELS = frozenset({"debug", "info", "warning", "error", "critical"})


def _parse_version(version_str: str) -> tuple[int, int] | None:
    m = _VERSION_RE.match(str(version_str).strip())
    if not m:
        return None
    return int(m.group("major")), int(m.group("minor"))


def is_compatible(version_str: str) -> bool:
    """Return True if *version_str* is compatible with the current protocol version.

    Compatibility rule: same major version, minor <= current minor.
    """
    parsed = _parse_version(version_str)
    if parsed is None:
        return False
    current = _parse_version(PROTOCOL_VERSION)
    assert current is not None
    cur_major, cur_minor = current
    msg_major, msg_minor = parsed
    return msg_major == cur_major and msg_minor <= cur_minor


def validate_message(payload: Any) -> tuple[bool, list[str]]:
    """Validate *payload* against the BossCrafts Protocol v1 message envelope.

    Returns ``(ok, errors)`` where *errors* is an empty list when *ok* is True.
    """
    errors: list[str] = []

    if not isinstance(payload, dict):
        return False, ["payload must be a JSON object (dict)"]

    for field in sorted(_REQUIRED_FIELDS):
        if field not in payload:
            errors.append(f"missing required field: {field!r}")

    if errors:
        return False, errors

    pv = str(payload.get("protocol_version", "")).strip()
    if not _VERSION_RE.match(pv):
        errors.append(f"invalid protocol_version format: {pv!r}; expected MAJOR.MINOR")
    elif not is_compatible(pv):
        errors.append(
            f"protocol_version {pv!r} is not compatible with current version {PROTOCOL_VERSION!r}"
        )

    msg_type = str(payload.get("type", "")).strip().lower()
    if msg_type not in _VALID_TYPES:
        errors.append(f"invalid type: {msg_type!r}; must be one of {sorted(_VALID_TYPES)}")

    timestamp = str(payload.get("timestamp", "")).strip()
    if not timestamp:
        errors.append("'timestamp' must be a non-empty ISO 8601 string")

    if msg_type == "event":
        if not str(payload.get("source", "")).strip():
            errors.append("event messages require a non-empty 'source' field")
        if not str(payload.get("event", "")).strip():
            errors.append("event messages require a non-empty 'event' field")
        level = str(payload.get("level", "info")).strip().lower()
        if level not in _VALID_LEVELS:
            errors.append(f"invalid level: {level!r}; must be one of {sorted(_VALID_LEVELS)}")
    elif msg_type == "command":
        if not str(payload.get("target", "")).strip():
            errors.append("command messages require a non-empty 'target' field")
        if not str(payload.get("command", "")).strip():
            errors.append("command messages require a non-empty 'command' field")

    return len(errors) == 0, errors


def wrap_event(
    source: str,
    event: str,
    data: dict[str, Any] | None = None,
    level: str = "info",
) -> dict[str, Any]:
    """Build a protocol v1-compliant event envelope."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": "event",
        "source": source,
        "event": event,
        "level": level,
        "data": data or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def wrap_command(
    target: str,
    command: str,
    args: dict[str, Any] | None = None,
    issued_by: str = "cli",
) -> dict[str, Any]:
    """Build a protocol v1-compliant command envelope."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": "command",
        "target": target,
        "command": command,
        "args": args or {},
        "issued_by": issued_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def load_schema() -> dict[str, Any]:
    """Load the raw JSON Schema file for Protocol v1."""
    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load protocol v1 schema: {exc}") from exc
