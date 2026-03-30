import argparse
import json
import os
import subprocess


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def unblock_file(path: str) -> dict:
    from sandbox import is_path_safe

    if not is_path_safe(path):
        return {"ok": False, "action": "unblock_file", "error": "sandbox_refused", "path": path}
    if not os.path.exists(path):
        return {"ok": False, "action": "unblock_file", "error": "file_not_found", "path": path}

    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Unblock-File -LiteralPath $args[0]",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            return {"ok": True, "action": "unblock_file", "path": path}
        return {
            "ok": False,
            "action": "unblock_file",
            "path": path,
            "returncode": proc.returncode,
            "stderr": proc.stderr.strip(),
        }
    except Exception as ex:
        return {"ok": False, "action": "unblock_file", "path": path, "error": str(ex)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge file unblock utility")
    parser.add_argument("--path", required=True, type=str, help="Path to downloaded file to unblock")
    args = parser.parse_args()

    result = unblock_file(args.path)
    _emit(result)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()