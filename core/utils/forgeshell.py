import argparse
import json
import shlex
import time
from pathlib import Path
from typing import Any

from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.state.os_state import build_os_state


try:
        import readline
except ImportError:  # pragma: no cover - readline can be unavailable on some runtimes
        readline = None


HELP_TEXT = """ForgeShell commands:
  help                          Show this help
  exit | quit                   Exit shell
  events [N]                    Show latest N events (default 20)
    watch-events [seconds]        Stream latest events every N seconds (default 2)
  state [name]                  Show all state keys or one state payload
  os-state [events]             Show canonical OS state snapshot
  send <target> <cmd> [JSON]    Emit bus command with optional JSON args
"""


def _pretty(payload: Any) -> None:
    print(json.dumps(payload, indent=2))


def _parse_json_or_empty(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("args payload must be a JSON object")
    return parsed


def _enable_readline_completion(bus: RuneBus) -> None:
    if readline is None:
        return

    commands = ["help", "exit", "quit", "events", "watch-events", "state", "os-state", "send"]

    def _choices(text: str) -> list[str]:
        line = readline.get_line_buffer()
        tokens = shlex.split(line) if line.strip() else []
        if not tokens:
            return [item for item in commands if item.startswith(text)]

        if len(tokens) == 1 and not line.endswith(" "):
            return [item for item in commands if item.startswith(tokens[0])]

        head = tokens[0]
        if head == "state":
            keys = sorted([p.stem for p in bus.state.glob("*.json")])
            return [item for item in keys if item.startswith(text)]
        if head == "send":
            if len(tokens) <= 2:
                from core.agent_registry import list_all_agents

                agent_ids = sorted(list_all_agents().keys())
                return [item for item in agent_ids if item.startswith(text)]
            if len(tokens) == 3:
                return [item for item in ["status_ping", "run", "scan_workspace"] if item.startswith(text)]
        return [item for item in commands if item.startswith(text)]

    def _completer(text: str, state: int) -> str | None:
        opts = _choices(text)
        if state < len(opts):
            return opts[state]
        return None

    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")


def _watch_events(bus: RuneBus, interval_seconds: float = 2.0) -> None:
    known_ids: set[str] = set()
    print("watching events (Ctrl+C to stop)")
    while True:
        items = bus.read_latest_events(limit=40)
        new_items: list[dict[str, Any]] = []
        for item in reversed(items):
            event_key = "|".join(
                [
                    str(item.get("timestamp", "")),
                    str(item.get("source", "")),
                    str(item.get("event", "")),
                ]
            )
            if event_key in known_ids:
                continue
            known_ids.add(event_key)
            new_items.append(item)

        for item in new_items:
            stamp = str(item.get("timestamp", "?"))
            source = str(item.get("source", "?"))
            event = str(item.get("event", "?"))
            print(f"[{stamp}] {source} -> {event}")

        time.sleep(max(0.5, float(interval_seconds)))


def run_shell(root: Path | None = None) -> None:
    bus = RuneBus(root or resolve_root_from_env())
    _enable_readline_completion(bus)
    print("ForgeShell v0.1")
    print("Type 'help' for commands.")

    while True:
        try:
            line = input("forge> ").strip()
        except EOFError:
            print()
            return

        if not line:
            continue
        if line in {"exit", "quit"}:
            return
        if line == "help":
            print(HELP_TEXT)
            continue

        parts = shlex.split(line)
        cmd = parts[0]

        try:
            if cmd == "events":
                limit = int(parts[1]) if len(parts) > 1 else 20
                _pretty(bus.read_latest_events(limit=max(1, limit)))
                continue

            if cmd == "watch-events":
                delay = float(parts[1]) if len(parts) > 1 else 2.0
                try:
                    _watch_events(bus, interval_seconds=delay)
                except KeyboardInterrupt:
                    print()
                    print("stopped watching events")
                continue

            if cmd == "state":
                if len(parts) == 1:
                    keys = sorted([p.stem for p in bus.state.glob("*.json")])
                    _pretty({"keys": keys})
                else:
                    name = parts[1]
                    path = bus.state / f"{name}.json"
                    if not path.exists():
                        _pretty({"ok": False, "message": f"state not found: {name}"})
                    else:
                        _pretty(json.loads(path.read_text(encoding="utf-8")))
                continue

            if cmd == "os-state":
                event_limit = int(parts[1]) if len(parts) > 1 else 30
                _pretty(build_os_state(root=bus.root, event_limit=max(1, event_limit)))
                continue

            if cmd == "send":
                if len(parts) < 3:
                    _pretty({"ok": False, "message": "usage: send <target> <cmd> [JSON]"})
                    continue
                target = parts[1]
                command_name = parts[2]
                args_json = line.split(command_name, 1)[1].strip()
                maybe_json = ""
                if args_json.startswith("{"):
                    maybe_json = args_json
                args = _parse_json_or_empty(maybe_json)
                path = bus.emit_command(target=target, command=command_name, args=args, issued_by="forgeshell")
                _pretty({"ok": True, "written": str(path)})
                continue

            _pretty({"ok": False, "message": f"unknown command: {cmd}"})
        except Exception as ex:
            _pretty({"ok": False, "error": str(ex)})


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS ForgeShell prototype")
    parser.add_argument("--root", default="", help="Optional BossForge root path")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else None
    run_shell(root=root)


if __name__ == "__main__":
    main()
