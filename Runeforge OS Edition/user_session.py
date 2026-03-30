import argparse
import ctypes
import json
import os


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def lock() -> dict:
    try:
        ctypes.windll.user32.LockWorkStation()
        return {"ok": True, "action": "lock"}
    except Exception as ex:
        return {"ok": False, "action": "lock", "error": str(ex)}


def logoff() -> dict:
    rc = os.system("shutdown -l")
    return {"ok": rc == 0, "action": "logoff", "returncode": rc}


def shutdown() -> dict:
    rc = os.system("shutdown /s /t 1")
    return {"ok": rc == 0, "action": "shutdown", "returncode": rc}


def restart() -> dict:
    rc = os.system("shutdown /r /t 1")
    return {"ok": rc == 0, "action": "restart", "returncode": rc}


def sleep() -> dict:
    rc = os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return {"ok": rc == 0, "action": "sleep", "returncode": rc}


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge user session utility")
    parser.add_argument("--lock", action="store_true", help="Lock current user session")
    parser.add_argument("--logoff", action="store_true", help="Log off current user")
    parser.add_argument("--shutdown", action="store_true", help="Shut down machine")
    parser.add_argument("--restart", action="store_true", help="Restart machine")
    parser.add_argument("--sleep", action="store_true", help="Sleep machine")
    args = parser.parse_args()

    selected = sum(bool(v) for v in [args.lock, args.logoff, args.shutdown, args.restart, args.sleep])
    if selected != 1:
        _emit(
            {
                "ok": False,
                "error": "Exactly one action flag is required",
                "allowed": ["--lock", "--logoff", "--shutdown", "--restart", "--sleep"],
            }
        )
        raise SystemExit(2)

    if args.lock:
        result = lock()
    elif args.logoff:
        result = logoff()
    elif args.shutdown:
        result = shutdown()
    elif args.restart:
        result = restart()
    elif args.sleep:
        result = sleep()
    else:
        result = {"ok": False, "error": "no_action_selected"}

    _emit(result)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
