import argparse
import ctypes
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from core.archivist_agent import ArchivistAgent
from core.rune_bus import RuneBus, resolve_root_from_env
from modules.os_snapshot import snapshot_all


AGENTS = {
    "hearth": "hearth_tender",
    "hearth_tender": "hearth_tender",
    "archivist": "archivist",
    "model": "model_gateway",
    "model_gateway": "model_gateway",
    "ai_gateway": "model_gateway",
    "llm_gateway": "model_gateway",
    "security": "security_sentinel",
    "security_sentinel": "security_sentinel",
    "codemage": "codemage",
    "runeforge": "runeforge",
    "devlot": "devlot",
    "model-keeper": "model_keeper",  # CLI alias for compatibility layer
    "speaker": "speaker",
    "model_keeper": "model_keeper",
}

PLUGIN_LOAD_STATE: list[dict[str, str]] = []


def _rituals_dir() -> Path:
    root = resolve_root_from_env()
    rituals = root / "cli" / "rituals"
    rituals.mkdir(parents=True, exist_ok=True)
    return rituals


def _plugin_dirs() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    repo_plugins = repo_root / "plugins" / "cli"
    user_plugins = resolve_root_from_env() / "cli" / "plugins"
    return [repo_plugins, user_plugins]


def _load_plugins(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> list[dict[str, str]]:
    loaded: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    for directory in _plugin_dirs():
        if not directory.exists():
            continue

        for file in sorted(directory.glob("*.py")):
            path_key = str(file.resolve()).lower()
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            module_name = f"bforge_plugin_{file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec is None or spec.loader is None:
                    loaded.append({"name": file.stem, "status": "error", "detail": "unable to load spec"})
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                register = getattr(module, "register", None)
                if register is None:
                    loaded.append({"name": file.stem, "status": "skipped", "detail": "missing register(subparsers)"})
                    continue

                register(subparsers)
                loaded.append({"name": file.stem, "status": "loaded", "detail": str(file)})
            except Exception as ex:
                loaded.append({"name": file.stem, "status": "error", "detail": str(ex)})

    return loaded


def pretty(data: Dict[str, Any]) -> None:
    print(json.dumps(data, indent=2))


def cmd_status(_: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())
    latest = bus.read_latest_events(limit=10)
    out = {
        "bus_root": str(bus.root),
        "events_found": len(latest),
        "latest_events": latest,
    }
    pretty(out)


    # Model-Keeper compatibility alias
    p_model_keeper = subparsers.add_parser("model-keeper", help="Model-Keeper compatibility commands")
    p_model_keeper.add_argument("action", choices=["status"], help="Action to perform")
    p_model_keeper.set_defaults(func=cmd_model_keeper)

def cmd_tail(args: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())
    for event in bus.read_latest_events(limit=args.limit):
        print(f"[{event.get('timestamp')}] {event.get('source')} -> {event.get('event')}")


def cmd_agent(args: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())
    target = AGENTS.get(args.agent, args.agent)
    parsed_args: Dict[str, Any] = {}
    if args.args:
        parsed_args = json.loads(args.args)
    path = bus.emit_command(target=target, command=args.command, args=parsed_args)
    print(f"command written: {path}")


def cmd_os(args: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())
    if args.sub == "snapshot":
        pretty(snapshot_all())
        return

    if args.sub == "daemon":
        action_map = {
            "light-prune": "light_prune",
            "full-prune": "full_prune",
            "compact-wsl": "compact_vhdx",
            "status-ping": "status_ping",
        }
        command = action_map[args.action]
        path = bus.emit_command("hearth_tender", command, {})
        print(f"daemon command queued: {path}")
        return

    raise SystemExit("unknown os command")


def cmd_ritual(args: argparse.Namespace) -> None:
    rituals = _rituals_dir()

    if args.sub == "list":
        found = sorted(rituals.glob("*.json"))
        if not found:
            print("no rituals found")
            return
        for item in found:
            print(item.stem)
        return

    if args.sub == "record":
        print("Recording ritual. Type CLI commands without the 'bforge' prefix.")
        print("Type 'done' when finished.")
        lines: list[str] = []
        while True:
            line = input("ritual> ").strip()
            if line in {"done", "exit", "quit"}:
                break
            if line:
                lines.append(line)

        path = rituals / f"{args.name}.json"
        path.write_text(json.dumps({"name": args.name, "commands": lines}, indent=2), encoding="utf-8")
        print(f"ritual saved: {path}")
        return

    if args.sub == "play":
        path = rituals / f"{args.name}.json"
        if not path.exists():
            raise SystemExit(f"ritual not found: {args.name}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        commands = payload.get("commands", [])
        parser = build_parser()

        for line in commands:
            try:
                sub_args = parser.parse_args(line.split())
            except SystemExit:
                print(f"skipping invalid ritual line: {line}")
                continue
            if not hasattr(sub_args, "func"):
                print(f"skipping incomplete ritual line: {line}")
                continue
            print(f"> {line}")
            sub_args.func(sub_args)
        return

    raise SystemExit("unknown ritual command")


def cmd_shell(_: argparse.Namespace) -> None:
    parser = build_parser()
    print("BossForge interactive shell. Type 'help' for commands, 'exit' to quit.")

    while True:
        line = input("bforge> ").strip()
        if line in {"exit", "quit"}:
            return
        if line == "help":
            parser.print_help()
            continue
        if not line:
            continue
        try:
            args = parser.parse_args(line.split())
        except SystemExit:
            continue
        if not hasattr(args, "func"):
            parser.print_help()
            continue
        args.func(args)


def cmd_plugins(_: argparse.Namespace) -> None:
    if not PLUGIN_LOAD_STATE:
        print("no plugins loaded")
        return

    for item in PLUGIN_LOAD_STATE:
        print(f"{item['status']:>7}  {item['name']}  {item['detail']}")


def _assignment_path() -> Path:
    bus = RuneBus(resolve_root_from_env())
    return bus.state / "agent_file_assignments.json"


def _load_assignments() -> dict[str, Any]:
    path = _assignment_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                items = payload.get("items", [])
                if isinstance(items, list):
                    return {"items": items}
        except (OSError, json.JSONDecodeError):
            pass
    return {"items": []}


def _save_assignments(payload: dict[str, Any]) -> None:
    path = _assignment_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cmd_assign(args: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())
    payload = _load_assignments()
    items = payload.get("items", [])

    if args.sub == "list":
        pretty({"ok": True, "assignments": items})
        return

    if args.sub == "set":
        target = Path(args.path).expanduser().resolve()
        if not target.exists():
            raise SystemExit(f"path does not exist: {target}")

        agent = AGENTS.get(args.agent, args.agent)
        entry = {
            "path": str(target),
            "agent": agent,
            "recursive": bool(args.recursive),
            "notes": args.notes or "",
        }

        updated: list[dict[str, Any]] = []
        replaced = False
        for item in items:
            if isinstance(item, dict) and str(item.get("path", "")).lower() == str(target).lower():
                updated.append(entry)
                replaced = True
            else:
                updated.append(item)
        if not replaced:
            updated.append(entry)

        payload["items"] = updated
        _save_assignments(payload)
        bus.write_state("agent_file_assignments", payload)
        bus.emit_event("bforge", "assignment:set", entry)

        if agent == "archivist":
            project_path = str(target.parent if target.is_file() else target)
            bus.emit_command("archivist", "add_project", {"path": project_path}, issued_by="bforge")

        pretty({"ok": True, "assignment": entry})
        return

    if args.sub == "remove":
        target = Path(args.path).expanduser().resolve()
        kept = [
            item
            for item in items
            if not (isinstance(item, dict) and str(item.get("path", "")).lower() == str(target).lower())
        ]
        payload["items"] = kept
        _save_assignments(payload)
        bus.write_state("agent_file_assignments", payload)
        bus.emit_event("bforge", "assignment:remove", {"path": str(target)})
        pretty({"ok": True, "removed_path": str(target)})
        return

    raise SystemExit("unknown assign command")


def cmd_security(args: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())

    if args.sub == "scan":
        path = bus.emit_command("security_sentinel", "scan_workspace", {"path": args.path}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "secrets-list":
        path = bus.emit_command("security_sentinel", "list_secrets", {}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "secret-set":
        path = bus.emit_command(
            "security_sentinel",
            "set_secret",
            {"name": args.name, "value": args.value},
            issued_by="bforge",
        )
        print(f"command written: {path}")
        return

    if args.sub == "secret-get":
        path = bus.emit_command(
            "security_sentinel",
            "get_secret",
            {"name": args.name, "reveal": args.reveal},
            issued_by="bforge",
        )
        print(f"command written: {path}")
        return

    if args.sub == "secret-delete":
        path = bus.emit_command("security_sentinel", "delete_secret", {"name": args.name}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "oauth-set":
        payload = {
            "provider": args.provider,
            "access_token": args.access_token,
            "refresh_token": args.refresh_token,
            "expires_at": args.expires_at,
        }
        path = bus.emit_command("security_sentinel", "set_oauth_token", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "oauth-get":
        path = bus.emit_command(
            "security_sentinel",
            "get_oauth_token",
            {"provider": args.provider, "reveal": args.reveal},
            issued_by="bforge",
        )
        print(f"command written: {path}")
        return

    if args.sub == "policy-set":
        actions = [item.strip() for item in (args.actions or "").split(",") if item.strip()]
        path = bus.emit_command(
            "security_sentinel",
            "set_policy",
            {"agent": args.agent, "actions": actions},
            issued_by="bforge",
        )
        print(f"command written: {path}")
        return

    if args.sub == "policy-check":
        path = bus.emit_command(
            "security_sentinel",
            "check_policy",
            {"agent": args.agent, "action": args.action},
            issued_by="bforge",
        )
        print(f"command written: {path}")
        return

    raise SystemExit("unknown security command")


def _resolve_project_path(path_arg: str | None) -> Path:
    raw = path_arg.strip() if path_arg else os.getcwd()
    target = Path(raw).expanduser().resolve()
    if not target.exists():
        raise SystemExit(f"path does not exist: {target}")
    return target.parent if target.is_file() else target


def _run_git(project_path: Path, args: list[str]) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(["git", "-C", str(project_path), *args], text=True, stderr=subprocess.STDOUT)
        return True, out.strip()
    except Exception as ex:
        return False, str(ex)


def _is_git_repo(project_path: Path) -> bool:
    ok, out = _run_git(project_path, ["rev-parse", "--is-inside-work-tree"])
    return ok and out.lower().strip() == "true"


def _init_repo_for_stewardship(project_path: Path) -> tuple[bool, str]:
    if not _is_git_repo(project_path):
        ok_init, out_init = _run_git(project_path, ["init"])
        if not ok_init:
            return False, f"failed to initialize git repo: {out_init}"

    ok_add, out_add = _run_git(project_path, ["add", "-A"])
    if not ok_add:
        return False, f"failed to stage repository files: {out_add}"
    return True, "git repo ready and files staged"


def cmd_summon(args: argparse.Namespace) -> None:
    if args.agent != "archivist":
        raise SystemExit(f"summon currently supports archivist only, got: {args.agent}")

    project_path = _resolve_project_path(args.path)

    if args.init_repo:
        ok_repo, repo_msg = _init_repo_for_stewardship(project_path)
        if not ok_repo:
            print(f"repository bootstrap warning: {repo_msg}")
        else:
            print(f"repository bootstrap: {repo_msg}")

    archivist = ArchivistAgent()
    onboard = archivist.add_onboarded_project(str(project_path))
    if not onboard.get("ok"):
        raise SystemExit(onboard.get("message", "failed to onboard project"))

    result = archivist.on_invoke()
    print(f"Archivist summoned for: {project_path}")
    pretty(result)

    ledger = _find_latest_ledger(result)
    if args.open_ledger and ledger:
        try:
            os.startfile(ledger)  # type: ignore[attr-defined]
        except Exception:
            pass

    if not args.no_notify:
        _notify_summon(project_path, ledger, result)


def cmd_seal(args: argparse.Namespace) -> None:
    archivist = ArchivistAgent()

    if args.sub == "preview":
        pretty(archivist.preview_seal())
        return

    if args.sub == "approve":
        result = archivist.approve_seal(
            seal_id=args.seal_id or None,
            commit_message=args.message or None,
            push=args.push,
            init_repo_if_missing=not args.no_init_repo,
        )
        pretty(result)
        return

    if args.sub == "reject":
        result = archivist.reject_seal(seal_id=args.seal_id or None, reason=args.reason or None)
        pretty(result)
        return

    raise SystemExit("unknown seal command")


def cmd_model(args: argparse.Namespace) -> None:
    bus = RuneBus(resolve_root_from_env())

    if args.sub == "list":
        path = bus.emit_command("model_gateway", "list_endpoints", {}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "agents":
        path = bus.emit_command("model_gateway", "list_agents", {}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "agent-create":
        tools = [item.strip() for item in (args.tools or "").split(",") if item.strip()]
        payload = {
            "name": args.name,
            "endpoint": args.endpoint,
            "system": args.system,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "tools": tools,
        }
        path = bus.emit_command("model_gateway", "create_agent", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "agent-delete":
        path = bus.emit_command("model_gateway", "delete_agent", {"name": args.name}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "agent-run":
        payload = {
            "name": args.name,
            "task": args.task,
            "endpoint": args.endpoint,
        }
        path = bus.emit_command("model_gateway", "run_agent", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "mcp-list":
        path = bus.emit_command("model_gateway", "list_mcp_servers", {}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "mcp-set":
        args_list = [item.strip() for item in (args.args_csv or "").split(",") if item.strip()]
        env_obj: Dict[str, str] = {}
        for pair in [item.strip() for item in (args.env_csv or "").split(",") if item.strip()]:
            if "=" in pair:
                key, value = pair.split("=", 1)
                env_obj[key.strip()] = value.strip()
        payload = {
            "name": args.name,
            "command": args.command,
            "args": args_list,
            "env": env_obj,
        }
        path = bus.emit_command("model_gateway", "set_mcp_server", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "mcp-remove":
        path = bus.emit_command("model_gateway", "remove_mcp_server", {"name": args.name}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "export":
        payload = {
            "file": args.file,
            "format": args.format,
        }
        path = bus.emit_command("model_gateway", "export_config", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "import":
        payload = {
            "file": args.file,
            "format": args.format,
            "merge": args.merge,
        }
        path = bus.emit_command("model_gateway", "import_config", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "set-endpoint":
        payload: Dict[str, Any] = {
            "name": args.name,
            "provider": args.provider,
            "url": args.url,
            "model": args.model,
            "api_key_env": args.api_key_env,
        }
        path = bus.emit_command("model_gateway", "set_endpoint", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "remove-endpoint":
        path = bus.emit_command("model_gateway", "remove_endpoint", {"name": args.name}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "invoke":
        payload = {
            "endpoint": args.endpoint,
            "prompt": args.prompt,
            "system": args.system,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
        }
        path = bus.emit_command("model_gateway", "invoke", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "refactor":
        code = args.code
        if args.code_file:
            code = Path(args.code_file).read_text(encoding="utf-8")
        if not code:
            raise SystemExit("provide --code or --code-file")

        payload = {
            "endpoint": args.endpoint,
            "language": args.language,
            "instructions": args.instructions,
            "code": code,
            "system": args.system,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
        }
        path = bus.emit_command("model_gateway", "refactor_code", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "servers":
        path = bus.emit_command("model_gateway", "list_servers", {}, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "serve":
        payload = {
            "server": args.server,
            "model": args.model,
            "host": args.host,
            "port": args.port,
        }
        path = bus.emit_command("model_gateway", "serve_model", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "stop":
        payload = {"server": args.server}
        path = bus.emit_command("model_gateway", "stop_model_server", payload, issued_by="bforge")
        print(f"command written: {path}")
        return

    if args.sub == "stop-all":
        path = bus.emit_command("model_gateway", "stop_all_model_servers", {}, issued_by="bforge")
        print(f"command written: {path}")
        return

    raise SystemExit("unknown model command")


def _find_latest_ledger(result: Dict[str, Any]) -> str:
    docs = result.get("doc_updates", [])
    if not isinstance(docs, list):
        return ""
    ledgers = [str(p) for p in docs if isinstance(p, str) and p.lower().endswith("daily_ledger.md")]
    return ledgers[-1] if ledgers else ""


def _notify_summon(project_path: Path, ledger_path: str, result: Dict[str, Any]) -> None:
    if os.name != "nt":
        return
    msg = (
        f"Archivist summoned for:\n{project_path}\n\n"
        f"Docs Updated: {len(result.get('doc_updates', []))}\n"
        f"Delegations: {result.get('delegation_notes', 0)}\n"
        f"Ledger: {ledger_path or 'n/a'}"
    )
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, "BossForgeOS - Archivist", 0x40)
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BossForgeOS CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_status = sub.add_parser("status")
    p_status.set_defaults(func=cmd_status)

    p_tail = sub.add_parser("tail")
    p_tail.add_argument("--limit", type=int, default=20)
    p_tail.set_defaults(func=cmd_tail)

    p_agent = sub.add_parser("agent")
    p_agent.add_argument("agent")
    p_agent.add_argument("command")
    p_agent.add_argument("--args", default="{}")
    p_agent.set_defaults(func=cmd_agent)

    p_os = sub.add_parser("os")
    p_os_sub = p_os.add_subparsers(dest="sub")

    p_snap = p_os_sub.add_parser("snapshot")
    p_snap.set_defaults(func=cmd_os)

    p_daemon = p_os_sub.add_parser("daemon")
    p_daemon.add_argument("action", choices=["compact-wsl", "light-prune", "full-prune", "status-ping"])
    p_daemon.set_defaults(func=cmd_os)

    p_shell = sub.add_parser("shell")
    p_shell.set_defaults(func=cmd_shell)

    p_ritual = sub.add_parser("ritual")
    p_ritual_sub = p_ritual.add_subparsers(dest="sub")

    p_ritual_record = p_ritual_sub.add_parser("record")
    p_ritual_record.add_argument("name")
    p_ritual_record.set_defaults(func=cmd_ritual)

    p_ritual_play = p_ritual_sub.add_parser("play")
    p_ritual_play.add_argument("name")
    p_ritual_play.set_defaults(func=cmd_ritual)

    p_ritual_list = p_ritual_sub.add_parser("list")
    p_ritual_list.set_defaults(func=cmd_ritual)

    p_plugins = sub.add_parser("plugins")
    p_plugins.set_defaults(func=cmd_plugins)

    p_summon = sub.add_parser("summon")
    p_summon.add_argument("agent", help="Agent to summon (currently: archivist)")
    p_summon.add_argument("--path", default="", help="Optional file/folder path to onboard; defaults to current directory")
    p_summon.add_argument("--init-repo", action="store_true", help="Initialize git repo for folder targets and stage all files before stewardship")
    p_summon.add_argument("--no-notify", action="store_true", help="Disable summon completion popup")
    p_summon.add_argument("--open-ledger", action="store_true", help="Open latest daily ledger after summon")
    p_summon.set_defaults(func=cmd_summon)

    p_seal = sub.add_parser("seal", help="Direct Archivist seal queue operations")
    p_seal_sub = p_seal.add_subparsers(dest="sub")

    p_seal_preview = p_seal_sub.add_parser("preview", help="Show pending and historical seals")
    p_seal_preview.set_defaults(func=cmd_seal)

    p_seal_approve = p_seal_sub.add_parser("approve", help="Approve latest or selected seal")
    p_seal_approve.add_argument("--seal-id", default="", help="Specific seal id; defaults to latest pending")
    p_seal_approve.add_argument("--message", default="", help="Override commit message")
    p_seal_approve.add_argument("--push", action="store_true", help="Push after successful commit")
    p_seal_approve.add_argument("--no-init-repo", action="store_true", help="Do not initialize git repo when missing")
    p_seal_approve.set_defaults(func=cmd_seal)

    p_seal_reject = p_seal_sub.add_parser("reject", help="Reject latest or selected seal")
    p_seal_reject.add_argument("--seal-id", default="", help="Specific seal id; defaults to latest pending")
    p_seal_reject.add_argument("--reason", default="", help="Reason for rejection")
    p_seal_reject.set_defaults(func=cmd_seal)

    p_model = sub.add_parser("model", help="Queue model gateway requests (Ollama/vLLM/LM Studio)")
    p_model_sub = p_model.add_subparsers(dest="sub")

    p_model_list = p_model_sub.add_parser("list", help="List configured model endpoints")
    p_model_list.set_defaults(func=cmd_model)

    p_model_agents = p_model_sub.add_parser("agents", help="List configured model-backed agent profiles")
    p_model_agents.set_defaults(func=cmd_model)

    p_model_agent_create = p_model_sub.add_parser("agent-create", help="Create/update a model-backed agent profile")
    p_model_agent_create.add_argument("name")
    p_model_agent_create.add_argument("--endpoint", required=True)
    p_model_agent_create.add_argument("--system", default="You are a helpful specialist agent.")
    p_model_agent_create.add_argument("--temperature", type=float, default=0.2)
    p_model_agent_create.add_argument("--max-tokens", type=int, default=900)
    p_model_agent_create.add_argument("--tools", default="", help="Comma-separated MCP server names")
    p_model_agent_create.set_defaults(func=cmd_model)

    p_model_agent_delete = p_model_sub.add_parser("agent-delete", help="Delete a model-backed agent profile")
    p_model_agent_delete.add_argument("name")
    p_model_agent_delete.set_defaults(func=cmd_model)

    p_model_agent_run = p_model_sub.add_parser("agent-run", help="Run a saved agent profile on a task")
    p_model_agent_run.add_argument("name")
    p_model_agent_run.add_argument("task")
    p_model_agent_run.add_argument("--endpoint", default="", help="Override agent endpoint for this run")
    p_model_agent_run.set_defaults(func=cmd_model)

    p_model_mcp_list = p_model_sub.add_parser("mcp-list", help="List configured MCP servers")
    p_model_mcp_list.set_defaults(func=cmd_model)

    p_model_mcp_set = p_model_sub.add_parser("mcp-set", help="Create/update an MCP server config")
    p_model_mcp_set.add_argument("name")
    p_model_mcp_set.add_argument("--command", required=True)
    p_model_mcp_set.add_argument("--args-csv", default="", help="Comma-separated command args")
    p_model_mcp_set.add_argument("--env-csv", default="", help="Comma-separated KEY=VALUE env pairs")
    p_model_mcp_set.set_defaults(func=cmd_model)

    p_model_mcp_remove = p_model_sub.add_parser("mcp-remove", help="Remove an MCP server config")
    p_model_mcp_remove.add_argument("name")
    p_model_mcp_remove.set_defaults(func=cmd_model)

    p_model_export = p_model_sub.add_parser("export", help="Export model config (endpoints/agents/mcp) to JSON or YAML")
    p_model_export.add_argument("file", help="Output file path (.json, .yaml, .yml)")
    p_model_export.add_argument("--format", default="", choices=["", "json", "yaml"], help="Optional format override")
    p_model_export.set_defaults(func=cmd_model)

    p_model_import = p_model_sub.add_parser("import", help="Import model config (endpoints/agents/mcp) from JSON or YAML")
    p_model_import.add_argument("file", help="Input file path (.json, .yaml, .yml)")
    p_model_import.add_argument("--format", default="", choices=["", "json", "yaml"], help="Optional format override")
    p_model_import.add_argument("--merge", action="store_true", help="Merge imported entries instead of replacing all")
    p_model_import.set_defaults(func=cmd_model)

    p_model_set = p_model_sub.add_parser("set-endpoint", help="Create or update an endpoint")
    p_model_set.add_argument("name", help="Endpoint key, e.g. ollama")
    p_model_set.add_argument("--provider", default="openai_compatible", choices=["openai_compatible", "ollama"])
    p_model_set.add_argument("--url", required=True)
    p_model_set.add_argument("--model", required=True)
    p_model_set.add_argument("--api-key-env", default="", help="Env var holding bearer token")
    p_model_set.set_defaults(func=cmd_model)

    p_model_remove = p_model_sub.add_parser("remove-endpoint", help="Delete an endpoint")
    p_model_remove.add_argument("name")
    p_model_remove.set_defaults(func=cmd_model)

    p_model_invoke = p_model_sub.add_parser("invoke", help="Send a prompt through a configured endpoint")
    p_model_invoke.add_argument("prompt")
    p_model_invoke.add_argument("--endpoint", default="ollama")
    p_model_invoke.add_argument("--system", default="You are BossForgeOS Model Gateway.")
    p_model_invoke.add_argument("--temperature", type=float, default=0.2)
    p_model_invoke.add_argument("--max-tokens", type=int, default=900)
    p_model_invoke.set_defaults(func=cmd_model)

    p_model_refactor = p_model_sub.add_parser("refactor", help="Ask model endpoint to refactor code")
    p_model_refactor.add_argument("--endpoint", default="ollama")
    p_model_refactor.add_argument("--language", default="python")
    p_model_refactor.add_argument("--instructions", default="Refactor for readability and maintainability.")
    p_model_refactor.add_argument("--code", default="")
    p_model_refactor.add_argument("--code-file", default="")
    p_model_refactor.add_argument(
        "--system",
        default="You are a senior software engineer. Return only the refactored code unless asked for explanation.",
    )
    p_model_refactor.add_argument("--temperature", type=float, default=0.1)
    p_model_refactor.add_argument("--max-tokens", type=int, default=1800)
    p_model_refactor.set_defaults(func=cmd_model)

    p_model_servers = p_model_sub.add_parser("servers", help="List tracked local model server processes")
    p_model_servers.set_defaults(func=cmd_model)

    p_model_serve = p_model_sub.add_parser("serve", help="Start a local model server runtime")
    p_model_serve.add_argument("server", choices=["ollama", "vllm", "lmstudio"])
    p_model_serve.add_argument("--model", default="", help="Model id/path; required for vllm")
    p_model_serve.add_argument("--host", default="127.0.0.1")
    p_model_serve.add_argument("--port", type=int, default=8000)
    p_model_serve.set_defaults(func=cmd_model)

    p_model_stop = p_model_sub.add_parser("stop", help="Stop one tracked model server")
    p_model_stop.add_argument("server", choices=["ollama", "vllm", "lmstudio"])
    p_model_stop.set_defaults(func=cmd_model)

    p_model_stop_all = p_model_sub.add_parser("stop-all", help="Stop all tracked model servers")
    p_model_stop_all.set_defaults(func=cmd_model)

    p_assign = sub.add_parser("assign", help="Assign an agent to a file/folder")
    p_assign_sub = p_assign.add_subparsers(dest="sub")

    p_assign_set = p_assign_sub.add_parser("set", help="Assign agent to path")
    p_assign_set.add_argument("path")
    p_assign_set.add_argument("--agent", required=True, help="agent key, e.g. archivist/codemage/devlot/runeforge/model_gateway")
    p_assign_set.add_argument("--recursive", action="store_true", help="mark folder assignment as recursive")
    p_assign_set.add_argument("--notes", default="", help="optional assignment notes")
    p_assign_set.set_defaults(func=cmd_assign)

    p_assign_remove = p_assign_sub.add_parser("remove", help="Remove assignment from path")
    p_assign_remove.add_argument("path")
    p_assign_remove.set_defaults(func=cmd_assign)

    p_assign_list = p_assign_sub.add_parser("list", help="List path assignments")
    p_assign_list.set_defaults(func=cmd_assign)

    p_security = sub.add_parser("security", help="Security Sentinel commands")
    p_security_sub = p_security.add_subparsers(dest="sub")

    p_security_scan = p_security_sub.add_parser("scan", help="Scan workspace for secret leaks")
    p_security_scan.add_argument("--path", default="")
    p_security_scan.set_defaults(func=cmd_security)

    p_security_list = p_security_sub.add_parser("secrets-list", help="List stored secret names")
    p_security_list.set_defaults(func=cmd_security)

    p_security_set = p_security_sub.add_parser("secret-set", help="Store secret value")
    p_security_set.add_argument("name")
    p_security_set.add_argument("value")
    p_security_set.set_defaults(func=cmd_security)

    p_security_get = p_security_sub.add_parser("secret-get", help="Get secret value (masked by default)")
    p_security_get.add_argument("name")
    p_security_get.add_argument("--reveal", action="store_true")
    p_security_get.set_defaults(func=cmd_security)

    p_security_del = p_security_sub.add_parser("secret-delete", help="Delete secret")
    p_security_del.add_argument("name")
    p_security_del.set_defaults(func=cmd_security)

    p_oauth_set = p_security_sub.add_parser("oauth-set", help="Store OAuth token payload")
    p_oauth_set.add_argument("provider")
    p_oauth_set.add_argument("access_token")
    p_oauth_set.add_argument("--refresh-token", default="")
    p_oauth_set.add_argument("--expires-at", default="")
    p_oauth_set.set_defaults(func=cmd_security)

    p_oauth_get = p_security_sub.add_parser("oauth-get", help="Read OAuth token payload")
    p_oauth_get.add_argument("provider")
    p_oauth_get.add_argument("--reveal", action="store_true")
    p_oauth_get.set_defaults(func=cmd_security)

    p_policy_set = p_security_sub.add_parser("policy-set", help="Set allowed actions for an agent")
    p_policy_set.add_argument("agent")
    p_policy_set.add_argument("--actions", default="", help="Comma-separated actions")
    p_policy_set.set_defaults(func=cmd_security)

    p_policy_check = p_security_sub.add_parser("policy-check", help="Check whether action is allowed for agent")
    p_policy_check.add_argument("agent")
    p_policy_check.add_argument("action")
    p_policy_check.set_defaults(func=cmd_security)

    global PLUGIN_LOAD_STATE
    PLUGIN_LOAD_STATE = _load_plugins(sub)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
