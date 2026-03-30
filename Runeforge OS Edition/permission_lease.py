import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
STATE_PATH = HERE / "permissions_state.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _default_state() -> dict[str, Any]:
    return {"version": "1.0", "grants": []}


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return _default_state()
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()
    if not isinstance(payload, dict):
        return _default_state()
    grants = payload.get("grants")
    if not isinstance(grants, list):
        payload["grants"] = []
    return payload


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _is_grant_active(grant: dict[str, Any], now: datetime) -> bool:
    if grant.get("revoked_at"):
        return False
    expires_at = _from_iso(grant.get("expires_at"))
    if expires_at is not None and now > expires_at:
        return False
    remaining_uses = grant.get("remaining_uses")
    if isinstance(remaining_uses, int) and remaining_uses <= 0:
        return False
    return True


def _cleanup_expired(state: dict[str, Any]) -> bool:
    now = _now_utc()
    changed = False
    for grant in state.get("grants", []):
        if grant.get("revoked_at"):
            continue
        expires_at = _from_iso(grant.get("expires_at"))
        if expires_at is not None and now > expires_at:
            grant["revoked_at"] = _iso(now)
            grant["revoked_reason"] = "expired"
            changed = True
    return changed


def grant_permission(params: dict[str, Any], issued_by: str = "command_code") -> dict[str, Any]:
    action_type = str(params.get("action_type", "")).strip()
    if not action_type:
        return {"ok": False, "message": "params.action_type is required"}

    agent = str(params.get("agent", "*")).strip() or "*"
    target_path = str(params.get("target_path", "")).strip() or None

    indefinite = bool(params.get("indefinite", False))
    duration_seconds_raw = params.get("duration_seconds")
    max_uses_raw = params.get("max_uses")

    duration_seconds: int | None = None
    if duration_seconds_raw is not None:
        try:
            duration_seconds = int(duration_seconds_raw)
        except Exception:
            return {"ok": False, "message": "params.duration_seconds must be an integer"}
        if duration_seconds <= 0:
            return {"ok": False, "message": "params.duration_seconds must be > 0"}

    max_uses: int | None = None
    if max_uses_raw is not None:
        try:
            max_uses = int(max_uses_raw)
        except Exception:
            return {"ok": False, "message": "params.max_uses must be an integer"}
        if max_uses <= 0:
            return {"ok": False, "message": "params.max_uses must be > 0"}

    now = _now_utc()
    expires_at = None if indefinite else (now + timedelta(seconds=duration_seconds)) if duration_seconds else None

    # Safe default for case-by-case approval if no duration/uses are provided.
    if not indefinite and duration_seconds is None and max_uses is None:
        max_uses = 1

    grant = {
        "id": f"grant_{uuid.uuid4().hex[:12]}",
        "action_type": action_type,
        "agent": agent,
        "target_path": target_path,
        "remaining_uses": max_uses,
        "created_at": _iso(now),
        "expires_at": _iso(expires_at),
        "revoked_at": None,
        "issued_by": issued_by,
    }

    state = load_state()
    _cleanup_expired(state)
    state.setdefault("grants", []).append(grant)
    save_state(state)
    return {"ok": True, "grant": grant}


def revoke_permission(grant_id: str, reason: str = "manual_revoke") -> dict[str, Any]:
    state = load_state()
    _cleanup_expired(state)
    now = _now_utc()
    for grant in state.get("grants", []):
        if str(grant.get("id")) != grant_id:
            continue
        if not grant.get("revoked_at"):
            grant["revoked_at"] = _iso(now)
            grant["revoked_reason"] = reason
            save_state(state)
        return {"ok": True, "grant": grant}
    return {"ok": False, "message": f"grant not found: {grant_id}"}


def list_permissions(active_only: bool = True) -> dict[str, Any]:
    state = load_state()
    changed = _cleanup_expired(state)
    now = _now_utc()
    grants = []
    for grant in state.get("grants", []):
        if active_only and not _is_grant_active(grant, now):
            continue
        grants.append(grant)
    if changed:
        save_state(state)
    return {"ok": True, "active_only": active_only, "grants": grants}


def _path_match(grant_path: str | None, params: dict[str, Any]) -> bool:
    if not grant_path:
        return True
    candidate_paths = []
    for key in ("path", "src", "dst"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            candidate_paths.append(value.strip())
    if not candidate_paths:
        return False
    gp = grant_path.lower()
    for cp in candidate_paths:
        lc = cp.lower()
        if lc == gp or lc.startswith(gp):
            return True
    return False


def authorize_action(action_type: str, params: dict[str, Any], agent: str, consume: bool = True) -> dict[str, Any]:
    state = load_state()
    changed = _cleanup_expired(state)
    now = _now_utc()

    for grant in state.get("grants", []):
        if not _is_grant_active(grant, now):
            continue
        g_action = str(grant.get("action_type", "")).strip()
        if g_action not in ("*", action_type):
            continue
        g_agent = str(grant.get("agent", "*")).strip() or "*"
        if g_agent not in ("*", agent):
            continue
        if not _path_match(grant.get("target_path"), params):
            continue

        remaining_uses = grant.get("remaining_uses")
        if consume and isinstance(remaining_uses, int) and remaining_uses > 0:
            grant["remaining_uses"] = remaining_uses - 1
            changed = True

        if changed:
            save_state(state)
        return {"authorized": True, "grant": grant}

    if changed:
        save_state(state)
    return {"authorized": False, "grant": None}