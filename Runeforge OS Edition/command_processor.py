import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PYTHON = sys.executable
LOGS_DIR = HERE / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

HIGH_RISK_ACTIONS = {
    "delete_file",
    "move_file",
    "copy_file",
    "set_volume",
    "registry_edit",
    "shutdown",
    "restart",
    "logoff",
    "unblock_file",
    "grant_permission",
    "revoke_permission",
    "format_disk",
}

LEASE_ELIGIBLE_ACTIONS = {
    "delete_file",
    "move_file",
    "copy_file",
    "set_volume",
    "registry_edit",
    "shutdown",
    "restart",
    "logoff",
    "unblock_file",
    "lock_file",
    "unlock_file",
}


def _collect_candidate_paths(params: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("path", "src", "dst"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    return paths


def _run_script(args: list[str], timeout_seconds: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [PYTHON, *args],
            cwd=str(HERE),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": [*args],
        }
    except Exception as ex:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(ex), "command": [*args]}


def _parse_last_json_line(text: str) -> dict[str, Any] | None:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _detect_tesseract() -> tuple[bool, str | None]:
    # Prefer explicit configured path when available.
    try:
        import pytesseract  # type: ignore

        configured = (getattr(pytesseract.pytesseract, "tesseract_cmd", "") or "").strip()
        if configured:
            if os.path.exists(configured):
                return True, None
            if shutil.which(configured):
                return True, None
            return False, f"Configured tesseract_cmd is not resolvable: {configured}"
    except Exception:
        # If pytesseract import fails, screen OCR is effectively unavailable.
        return False, "pytesseract is not importable in this environment"

    binary = shutil.which("tesseract")
    if binary:
        return True, None
    return False, "Native Tesseract binary not found on PATH"


def observe() -> dict[str, Any]:
    from sandbox import redact_sensitive

    obs: dict[str, Any] = {}

    sysinfo = _run_script(["system_info.py"])
    obs["system_info"] = redact_sensitive(sysinfo.get("stdout", "")) if sysinfo.get("ok") else sysinfo.get("stderr", "")

    uia = _run_script(["ui_tree_extractor.py"])
    if uia.get("ok"):
        try:
            obs["uia_tree"] = json.loads(uia.get("stdout", "") or "{}")
        except json.JSONDecodeError:
            obs["uia_tree"] = {"error": "invalid_json", "raw": uia.get("stdout", "")}
    else:
        obs["uia_tree"] = {"error": uia.get("stderr", "unknown error")}

    ocr_available, ocr_reason = _detect_tesseract()
    obs["ocr_available"] = ocr_available
    if not ocr_available:
        obs["ocr_status"] = ocr_reason

    shot_cmd = ["screenshot_tools.py", "--output-dir", str((HERE / "captures").resolve())]
    if ocr_available:
        shot_cmd.insert(1, "--ocr")

    shot = _run_script(shot_cmd, timeout_seconds=60)
    parsed = _parse_last_json_line(shot.get("stdout", "")) if shot.get("ok") else None
    if parsed:
        obs["screenshot_path"] = parsed.get("screenshot_path")
        if ocr_available:
            obs["ocr_text"] = redact_sensitive(str(parsed.get("ocr_text", "")))
        else:
            obs["ocr_text"] = f"[OCR unavailable: {ocr_reason}]"
    else:
        obs["screenshot_path"] = None
        if ocr_available:
            obs["ocr_text"] = f"[OCR error: {shot.get('stderr', 'no output')}]"
        else:
            obs["ocr_text"] = f"[OCR unavailable: {ocr_reason}]"

    return obs


def _confirm_high_risk(action: dict[str, Any], command_code: str | None) -> dict[str, Any]:
    atype = str(action.get("action_type", ""))
    if atype not in HIGH_RISK_ACTIONS:
        return {"ok": True}

    cmd = ["high_risk_action.py"]
    if command_code:
        cmd.extend(["--code", command_code])
    check = _run_script(cmd)
    if not check.get("ok"):
        return {
            "ok": False,
            "message": "High-risk action aborted",
            "guard": check,
        }
    return {"ok": True}


def execute_action(action: dict[str, Any], command_code: str | None = None, agent: str = "runeforge") -> dict[str, Any]:
    atype = str(action.get("action_type", ""))
    params = action.get("params", {}) if isinstance(action.get("params"), dict) else {}

    if atype == "grant_permission":
        guard = _confirm_high_risk(action, command_code)
        if not guard.get("ok"):
            return guard
        from permission_lease import grant_permission

        return {
            "ok": True,
            "action_type": atype,
            "result_parsed": grant_permission(params, issued_by="command_code"),
        }

    if atype == "revoke_permission":
        guard = _confirm_high_risk(action, command_code)
        if not guard.get("ok"):
            return guard
        from permission_lease import revoke_permission

        grant_id = str(params.get("grant_id", "")).strip()
        reason = str(params.get("reason", "manual_revoke")).strip() or "manual_revoke"
        return {
            "ok": True,
            "action_type": atype,
            "result_parsed": revoke_permission(grant_id=grant_id, reason=reason),
        }

    if atype == "list_permissions":
        from permission_lease import list_permissions

        active_only = bool(params.get("active_only", True))
        return {
            "ok": True,
            "action_type": atype,
            "result_parsed": list_permissions(active_only=active_only),
        }

    if atype == "list_file_locks":
        from file_lock import list_locks

        active_only = bool(params.get("active_only", True))
        return {
            "ok": True,
            "action_type": atype,
            "result_parsed": list_locks(active_only=active_only),
        }

    authorization: dict[str, Any] = {"mode": "none", "grant": None}

    if atype in LEASE_ELIGIBLE_ACTIONS:
        from permission_lease import authorize_action

        grant_match = authorize_action(action_type=atype, params=params, agent=agent, consume=True)
        if grant_match.get("authorized"):
            authorization = {"mode": "lease", "grant": grant_match.get("grant")}
        else:
            guard = _confirm_high_risk(action, command_code)
            if not guard.get("ok"):
                return guard
            authorization = {"mode": "command_code", "grant": None}

    # If a target path is command-locked, require command code or a file_lock_override lease.
    if atype not in {"lock_file", "unlock_file", "list_file_locks", "grant_permission", "revoke_permission", "list_permissions"}:
        candidate_paths = _collect_candidate_paths(params)
        if candidate_paths:
            from file_lock import get_lock_for_path
            from permission_lease import authorize_action

            for p in candidate_paths:
                active_lock = get_lock_for_path(p)
                if not active_lock:
                    continue

                override = authorize_action("file_lock_override", {"path": p}, agent=agent, consume=True)
                if override.get("authorized"):
                    authorization = {
                        "mode": "file_lock_override_lease",
                        "grant": override.get("grant"),
                        "lock": active_lock,
                    }
                    continue

                lock_guard = _confirm_high_risk({"action_type": "unlock_file"}, command_code)
                if not lock_guard.get("ok"):
                    return {
                        "ok": False,
                        "message": "path is command-locked and requires valid command code",
                        "locked_path": active_lock.get("path"),
                        "guard": lock_guard,
                    }
                authorization = {"mode": "file_lock_command_code", "grant": None, "lock": active_lock}

    dispatch: dict[str, list[str]] = {
        "open_app": ["app_control.py", "--open", str(params.get("path", ""))],
        "close_app": ["app_control.py", "--close", str(params.get("name", ""))],
        "delete_file": ["file_management.py", "--delete", str(params.get("path", ""))],
        "move_file": ["file_management.py", "--move", str(params.get("src", "")), str(params.get("dst", ""))],
        "copy_file": ["file_management.py", "--copy", str(params.get("src", "")), str(params.get("dst", ""))],
        "set_volume": ["set_volume.py", "--level", str(params.get("level", "")), "--trusted-caller"],
        "registry_edit": [
            "registry_tools.py",
            "--set",
            str(params.get("key_path", "")),
            str(params.get("value_name", "")),
            str(params.get("value", "")),
        ],
        "shutdown": ["user_session.py", "--shutdown"],
        "restart": ["user_session.py", "--restart"],
        "logoff": ["user_session.py", "--logoff"],
        "lock_file": ["file_lock.py", "--lock", str(params.get("path", "")), "--reason", str(params.get("reason", "command_lock"))],
        "unlock_file": ["file_lock.py", "--unlock", str(params.get("path", ""))],
        "unblock_file": ["file_unblock.py", "--path", str(params.get("path", ""))],
        "open_file": ["file_management.py", "--open", str(params.get("path", ""))],
        "list_directory": ["file_management.py", "--list", str(params.get("path", ""))],
        "open_url": ["app_control.py", "--open_url", str(params.get("url", ""))],
    }

    cmd = dispatch.get(atype)
    if not cmd:
        return {"ok": False, "message": f"unknown action: {atype}"}

    result = _run_script(cmd)
    parsed_result = _parse_last_json_line(result.get("stdout", ""))
    return {
        "ok": bool(result.get("ok")),
        "action_type": atype,
        "authorization": authorization,
        "result": result,
        "result_parsed": parsed_result,
    }


def log_episode_step(logfile: Path, step: dict[str, Any]) -> None:
    with logfile.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(step) + "\n")


def run_interactive(max_steps: int = 20) -> dict[str, Any]:
    logfile = LOGS_DIR / f"episode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    goal = input("Enter your task/goal: ").strip()
    done = False
    steps = 0

    while not done and steps < max_steps:
        obs = observe()
        print("Observation:", json.dumps(obs, indent=2)[:1500])
        action_json = input("Enter next action as JSON (or 'done'): ").strip()
        if action_json.lower() == "done":
            done = True
            break
        try:
            action = json.loads(action_json)
            exec_result = execute_action(action)
            step = {
                "step": steps,
                "goal": goal,
                "observation": obs,
                "action": action,
                "action_result": exec_result,
                "timestamp": datetime.now().isoformat(),
            }
            log_episode_step(logfile, step)
            print(json.dumps(exec_result, indent=2))
        except Exception as ex:
            print(f"Error: {ex}")
        steps += 1

    return {"ok": True, "mode": "interactive", "logfile": str(logfile), "steps": steps}


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge OS Command Processor")
    parser.add_argument("--observe", action="store_true", help="Emit one observation JSON payload and exit")
    parser.add_argument("--action-json", type=str, help="Execute one action JSON payload and exit")
    parser.add_argument("--action-file", type=str, help="Execute one action loaded from a JSON file")
    parser.add_argument("--command-code", type=str, help="Command code for high-risk action confirmation")
    parser.add_argument("--agent", type=str, default="runeforge", help="Logical caller identity for permission leases")
    parser.add_argument("--interactive", action="store_true", help="Run interactive loop mode")
    args = parser.parse_args()

    if args.observe:
        print(json.dumps({"ok": True, "observation": observe()}))
        return

    if args.action_json or args.action_file:
        if args.action_json:
            action = json.loads(args.action_json)
        else:
            action = json.loads(Path(args.action_file).read_text(encoding="utf-8"))
        result = execute_action(action=action, command_code=args.command_code, agent=args.agent)
        print(json.dumps(result))
        return

    if args.interactive:
        print(json.dumps(run_interactive()))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
