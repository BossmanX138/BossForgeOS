from __future__ import annotations

import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEDULER_FORBIDDEN_SHELL_CHARS = ("|", "&", ";", ">", "<", "$", "`")


def default_scheduler_state() -> dict[str, Any]:
    return {"jobs": [], "history": []}


def default_cicd_state() -> dict[str, Any]:
    return {"last_run": {}, "history": []}


def validate_scheduler_command(command: str) -> tuple[bool, str]:
    raw = str(command or "").strip()
    if not raw:
        return True, ""
    if any(token in raw for token in SCHEDULER_FORBIDDEN_SHELL_CHARS):
        return False, "command contains forbidden shell control characters"
    return True, ""


def split_scheduler_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=False)
    return [item for item in parts if str(item).strip()]


def scheduler_get(state: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **state}


def scheduler_post(state: dict[str, Any], payload: dict[str, Any], project_root: Path) -> tuple[dict[str, Any], int]:
    action = str(payload.get("action", "")).strip().lower()
    jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
    history = state.get("history") if isinstance(state.get("history"), list) else []

    if action == "add":
        label = str(payload.get("label", "")).strip() or "unnamed-job"
        command = str(payload.get("command", "")).strip()
        ok, error = validate_scheduler_command(command)
        if not ok:
            return {"ok": False, "message": error}, 400
        interval_seconds = max(30, int(payload.get("interval_seconds", 300)))
        job_id = f"job-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        jobs.append(
            {
                "id": job_id,
                "label": label,
                "command": command,
                "interval_seconds": interval_seconds,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["jobs"] = jobs
        state["history"] = history[-50:]
        return {"ok": True, "message": "job added", "job_id": job_id, **state}, 200

    if action == "remove":
        job_id = str(payload.get("id", "")).strip()
        if not job_id:
            return {"ok": False, "message": "id is required"}, 400
        state["jobs"] = [item for item in jobs if str(item.get("id", "")).strip() != job_id]
        return {"ok": True, "message": "job removed", **state}, 200

    if action == "run_now":
        job_id = str(payload.get("id", "")).strip()
        if not job_id:
            return {"ok": False, "message": "id is required"}, 400
        job = next((item for item in jobs if str(item.get("id", "")).strip() == job_id), None)
        if not isinstance(job, dict):
            return {"ok": False, "message": "job not found"}, 404

        command = str(job.get("command", "")).strip()
        if not command:
            result = {"ok": True, "message": "job has no command; treated as metadata-only task", "exit_code": 0}
        else:
            ok, error = validate_scheduler_command(command)
            if not ok:
                result = {"ok": False, "message": error, "exit_code": 2}
            else:
                try:
                    cmd_parts = split_scheduler_command(command)
                except ValueError as ex:
                    result = {"ok": False, "message": f"invalid command syntax: {ex}", "exit_code": 2}
                else:
                    if not cmd_parts:
                        result = {"ok": False, "message": "empty command after parsing", "exit_code": 2}
                    else:
                        try:
                            proc = subprocess.run(
                                cmd_parts,
                                cwd=str(project_root),
                                shell=False,
                                capture_output=True,
                                text=True,
                                timeout=300,
                            )
                            result = {
                                "ok": proc.returncode == 0,
                                "exit_code": proc.returncode,
                                "stdout": (proc.stdout or "")[-2000:],
                                "stderr": (proc.stderr or "")[-2000:],
                            }
                        except subprocess.TimeoutExpired as ex:
                            result = {
                                "ok": False,
                                "exit_code": 124,
                                "stdout": ((ex.stdout or "") if isinstance(ex.stdout, str) else "")[-2000:],
                                "stderr": ((ex.stderr or "") if isinstance(ex.stderr, str) else "")[-2000:],
                                "message": "command timed out",
                            }

        history.append(
            {
                "job_id": job_id,
                "label": str(job.get("label", "")).strip(),
                "ran_at": datetime.now(timezone.utc).isoformat(),
                **result,
            }
        )
        state["history"] = history[-100:]
        return {"ok": True, "message": "job executed", "result": result, **state}, 200

    return {"ok": False, "message": "unsupported scheduler action"}, 400


def cicd_get(state: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **state}


def cicd_post(state: dict[str, Any], payload: dict[str, Any], project_root: Path) -> tuple[dict[str, Any], int]:
    action = str(payload.get("action", "")).strip().lower()
    suite = str(payload.get("suite", "quick")).strip().lower()
    if action != "run":
        return {"ok": False, "message": "unsupported cicd action"}, 400

    if suite == "full":
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    else:
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

    proc = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
    result = {
        "suite": suite,
        "command": " ".join(cmd),
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-5000:],
        "stderr": (proc.stderr or "")[-5000:],
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }

    history = state.get("history") if isinstance(state.get("history"), list) else []
    history.append(result)
    state["last_run"] = result
    state["history"] = history[-30:]
    return {"ok": True, **state}, 200
