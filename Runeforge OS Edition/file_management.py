import argparse
import json
import os
import shutil
import subprocess
import sys


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def _safe(path: str) -> tuple[bool, dict]:
    from sandbox import is_path_safe

    if is_path_safe(path):
        return True, {}
    return False, {"ok": False, "error": "sandbox_refused", "path": path}


def create_file(path: str, content: str = "") -> dict:
    ok, err = _safe(path)
    if not ok:
        return err
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return {"ok": True, "action": "create_file", "path": path}
    except Exception as ex:
        return {"ok": False, "action": "create_file", "path": path, "error": str(ex)}


def delete_file(path: str) -> dict:
    ok, err = _safe(path)
    if not ok:
        return err
    try:
        if not os.path.exists(path):
            return {"ok": False, "action": "delete_file", "path": path, "error": "file_not_found"}
        os.remove(path)
        return {"ok": True, "action": "delete_file", "path": path}
    except Exception as ex:
        return {"ok": False, "action": "delete_file", "path": path, "error": str(ex)}


def move_file(src: str, dst: str) -> dict:
    ok1, err1 = _safe(src)
    ok2, err2 = _safe(dst)
    if not ok1:
        return err1
    if not ok2:
        return err2
    try:
        shutil.move(src, dst)
        return {"ok": True, "action": "move_file", "src": src, "dst": dst}
    except Exception as ex:
        return {"ok": False, "action": "move_file", "src": src, "dst": dst, "error": str(ex)}


def copy_file(src: str, dst: str) -> dict:
    ok1, err1 = _safe(src)
    ok2, err2 = _safe(dst)
    if not ok1:
        return err1
    if not ok2:
        return err2
    try:
        shutil.copy(src, dst)
        return {"ok": True, "action": "copy_file", "src": src, "dst": dst}
    except Exception as ex:
        return {"ok": False, "action": "copy_file", "src": src, "dst": dst, "error": str(ex)}


def list_directory(path: str) -> dict:
    ok, err = _safe(path)
    if not ok:
        return err
    try:
        if not os.path.isdir(path):
            return {"ok": False, "action": "list_directory", "path": path, "error": "not_a_directory"}
        items = sorted(os.listdir(path))
        return {"ok": True, "action": "list_directory", "path": path, "items": items}
    except Exception as ex:
        return {"ok": False, "action": "list_directory", "path": path, "error": str(ex)}


def open_file(path: str) -> dict:
    ok, err = _safe(path)
    if not ok:
        return err
    try:
        if not os.path.exists(path):
            return {"ok": False, "action": "open_file", "path": path, "error": "file_not_found"}
        os.startfile(path)
        return {"ok": True, "action": "open_file", "path": path}
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", path], shell=False)
            return {"ok": True, "action": "open_file", "path": path}
        except Exception as ex:
            return {"ok": False, "action": "open_file", "path": path, "error": str(ex)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Runeforge file management utility")
    parser.add_argument("--create", type=str, help="Create a file at PATH")
    parser.add_argument("--content", type=str, default="", help="Content for --create")
    parser.add_argument("--delete", type=str, help="Delete file at PATH")
    parser.add_argument("--move", nargs=2, metavar=("SRC", "DST"), help="Move file")
    parser.add_argument("--copy", nargs=2, metavar=("SRC", "DST"), help="Copy file")
    parser.add_argument("--list", type=str, help="List directory contents")
    parser.add_argument("--open", type=str, help="Open file with default app")
    args = parser.parse_args()

    selected = sum(
        bool(v)
        for v in [args.create, args.delete, args.move, args.copy, args.list, args.open]
    )
    if selected != 1:
        _emit(
            {
                "ok": False,
                "error": "Exactly one action flag is required",
                "allowed": ["--create", "--delete", "--move", "--copy", "--list", "--open"],
            }
        )
        raise SystemExit(2)

    if args.create:
        _emit(create_file(args.create, args.content))
        return
    if args.delete:
        _emit(delete_file(args.delete))
        return
    if args.move:
        _emit(move_file(args.move[0], args.move[1]))
        return
    if args.copy:
        _emit(copy_file(args.copy[0], args.copy[1]))
        return
    if args.list:
        _emit(list_directory(args.list))
        return
    _emit(open_file(args.open))


if __name__ == "__main__":
    main()
