import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
LOCKS_PATH = HERE / "file_locks.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(path: str) -> str:
    return str(Path(path).resolve())


def _load_state() -> dict[str, Any]:
    if not LOCKS_PATH.exists():
        return {"version": "1.0", "locks": []}
    try:
        payload = json.loads(LOCKS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": "1.0", "locks": []}
    if not isinstance(payload, dict):
        return {"version": "1.0", "locks": []}
    if not isinstance(payload.get("locks"), list):
        payload["locks"] = []
    return payload


def _save_state(state: dict[str, Any]) -> None:
    LOCKS_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload))


def lock_file(path: str, reason: str | None = None) -> dict[str, Any]:
    from sandbox import is_path_safe

    p = _norm(path)
    if not is_path_safe(p):
        return {"ok": False, "action": "lock_file", "error": "sandbox_refused", "path": p}

    state = _load_state()
    for item in state["locks"]:
        if str(item.get("path", "")).lower() == p.lower() and not item.get("revoked_at"):
            return {"ok": True, "action": "lock_file", "path": p, "already_locked": True, "lock": item}

    lock = {
        "path": p,
        "created_at": _now_iso(),
        "revoked_at": None,
        "reason": reason or "command_lock",
    }
    state["locks"].append(lock)
    _save_state(state)
    return {"ok": True, "action": "lock_file", "path": p, "lock": lock}


def unlock_file(path: str) -> dict[str, Any]:
    p = _norm(path)
    state = _load_state()
    for item in state["locks"]:
        if str(item.get("path", "")).lower() != p.lower():
            continue
        if not item.get("revoked_at"):
            item["revoked_at"] = _now_iso()
            _save_state(state)
            return {"ok": True, "action": "unlock_file", "path": p, "lock": item}
        return {"ok": True, "action": "unlock_file", "path": p, "already_unlocked": True, "lock": item}
    return {"ok": False, "action": "unlock_file", "path": p, "error": "not_locked"}


def list_locks(active_only: bool = True) -> dict[str, Any]:
    state = _load_state()
    out = []
    for item in state["locks"]:
        if active_only and item.get("revoked_at"):
            continue
        out.append(item)
    return {"ok": True, "action": "list_file_locks", "active_only": active_only, "locks": out}


def get_lock_for_path(path: str) -> dict[str, Any] | None:
    p = _norm(path)
    state = _load_state()
    for item in state["locks"]:
        if item.get("revoked_at"):
            continue
        locked_path = str(item.get("path", ""))
        if not locked_path:
            continue
        lp = locked_path.lower()
        cp = p.lower()
        if cp == lp or cp.startswith(lp.rstrip("\\/") + "\\") or cp.startswith(lp.rstrip("\\/") + "/"):
            return item
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge file lock utility")
    parser.add_argument("--lock", type=str, help="Lock a file/folder path")
    parser.add_argument("--unlock", type=str, help="Unlock a file/folder path")
    parser.add_argument("--status", type=str, help="Get lock status for a path")
    parser.add_argument("--list", action="store_true", help="List active locks")
    parser.add_argument("--list-all", action="store_true", help="List all locks including revoked")
    parser.add_argument("--reason", type=str, default="command_lock", help="Reason for --lock")
    args = parser.parse_args()

    selected = sum(bool(v) for v in [args.lock, args.unlock, args.status, args.list, args.list_all])
    if selected != 1:
        _emit(
            {
                "ok": False,
                "error": "Exactly one action flag is required",
                "allowed": ["--lock", "--unlock", "--status", "--list", "--list-all"],
            }
        )
        raise SystemExit(2)

    if args.lock:
        result = lock_file(args.lock, reason=args.reason)
    elif args.unlock:
        result = unlock_file(args.unlock)
    elif args.status:
        lock = get_lock_for_path(args.status)
        result = {"ok": True, "action": "lock_status", "path": _norm(args.status), "locked": lock is not None, "lock": lock}
    elif args.list:
        result = list_locks(active_only=True)
    else:
        result = list_locks(active_only=False)

    _emit(result)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()