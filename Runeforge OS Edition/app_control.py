import argparse
import json
import subprocess
import webbrowser
import psutil


def _emit(payload):
    print(json.dumps(payload))


def open_app(path):
    try:
        proc = subprocess.Popen(path)
        return {"ok": True, "action": "open_app", "path": path, "pid": proc.pid}
    except Exception as ex:
        return {"ok": False, "action": "open_app", "path": path, "error": str(ex)}


def open_url(url):
    ok = webbrowser.open(url)
    if ok:
        return {"ok": True, "action": "open_url", "url": url}
    return {"ok": False, "action": "open_url", "url": url, "error": "Unable to open URL"}

def close_app(process_name):
    closed = []
    errors = []
    for proc in psutil.process_iter(['name']):
        pname = proc.info.get('name')
        if pname and process_name.lower() in pname.lower():
            try:
                proc.terminate()
                closed.append({"pid": proc.pid, "name": pname})
            except Exception as ex:
                errors.append({"pid": proc.pid, "name": pname, "error": str(ex)})
    return {
        "ok": len(closed) > 0 and len(errors) == 0,
        "action": "close_app",
        "target": process_name,
        "closed": closed,
        "errors": errors,
    }

def list_running_apps():
    apps = []
    for proc in psutil.process_iter(['pid', 'name']):
        apps.append({"pid": proc.info.get('pid'), "name": proc.info.get('name')})
    return {"ok": True, "action": "list_running_apps", "processes": apps}


def main():
    parser = argparse.ArgumentParser(description="Runeforge app control utility")
    parser.add_argument("--open", type=str, help="Open an application path or command")
    parser.add_argument("--close", type=str, help="Close processes by name match")
    parser.add_argument("--list", action="store_true", help="List running processes")
    parser.add_argument("--open_url", type=str, help="Open URL in default browser")
    args = parser.parse_args()

    actions_selected = sum(
        bool(v)
        for v in [args.open, args.close, args.list, args.open_url]
    )
    if actions_selected != 1:
        _emit(
            {
                "ok": False,
                "error": "Exactly one action flag is required",
                "allowed": ["--open", "--close", "--list", "--open_url"],
            }
        )
        raise SystemExit(2)

    if args.open:
        _emit(open_app(args.open))
        return

    if args.close:
        _emit(close_app(args.close))
        return

    if args.list:
        _emit(list_running_apps())
        return

    _emit(open_url(args.open_url))

if __name__ == "__main__":
    main()
