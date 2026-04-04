import argparse
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from core.rune_bus import RuneBus, resolve_root_from_env

# GitHubConnector import
from core.github_connector import GitHubConnector


CODEMAGE_PROFILE: dict[str, Any] = {
    "id": "codemage",
    "name": "CodeMage, Arch-Scribe of the Forge",
    "version": "1.0.0",
    "description": "Arcane engineer for code and scroll interpretation in BossForge.",
    "persona": {
        "short_title": "Arcane Engineer and Scroll-Reader",
        "identity": [
            "You are CodeMage, Arch-Scribe of the BossCrafts Forge.",
            "You treat .md/.txt instructions as enchanted scrolls.",
            "You orchestrate apprentices to complete work safely and cleanly.",
        ],
        "tone": {"default": "precise, technical, mythic", "address": ["Bossman", "Bridge Builder"]},
        "oath": [
            "Favor clarity over cleverness.",
            "Refuse unsafe or contradictory work.",
            "Preserve original artifacts unless instructed otherwise.",
        ],
    },
    "apprentices": [
        {"id": "apprentice_a", "name": "Axiom", "role": "literalist"},
        {"id": "apprentice_b", "name": "Bricol", "role": "improviser"},
        {"id": "apprentice_c", "name": "Calibran", "role": "overseer"},
    ],
    "scroll_rituals": {
        "workspace_indexing": {"id": "workspace_indexing_ritual"},
        "scroll_reading": {"id": "scroll_reading_ritual"},
        "continue_rule": {"id": "continue_rule"},
    },
    "io": {
        "bus": {
            "commands_dir": "~/BossCrafts/bus/commands",
            "events_dir": "~/BossCrafts/bus/events",
            "state_dir": "~/BossCrafts/bus/state",
        },
        "cli": {
            "invoke_example": "bforge agent codemage status_ping",
            "agent_target": "codemage",
        },
    },
    "models": {
        "status": "active",
        "default_endpoint": "vllm",
        "inference": {
            "provider": "openai_compatible",
            "url": "http://127.0.0.1:8000/v1/chat/completions",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "api_key_env": "",
            "timeout_seconds": 8,
            "temperature": 0.2,
            "max_tokens": 700,
        },
    },
    "state_machine": {
        "initial_state": "Idle",
        "states": {
            "Idle": {"on_command": "WorkspaceIndexing"},
            "WorkspaceIndexing": {"on_success": "DetectScroll", "on_error": "Blocked"},
            "DetectScroll": {"on_scroll_found": "ReadingScroll", "on_no_scroll": "AwaitingUserDirection"},
            "ReadingScroll": {"on_parsed": "InterpretingIntent", "on_error": "Blocked"},
            "InterpretingIntent": {"on_clarity": "AssigningApprentices", "on_unclear": "AwaitingUserDirection"},
            "AssigningApprentices": {"on_planned": "PlanningExecution"},
            "PlanningExecution": {"on_confirmed": "Executing", "on_rejected": "AwaitingUserDirection"},
            "Executing": {"on_partial": "Continuing", "on_complete": "IntegratingWork", "on_error": "ConsultingApprentices"},
            "Continuing": {"on_more_work": "Executing", "on_done": "IntegratingWork"},
            "ConsultingApprentices": {"on_resolved": "Executing", "on_unresolved": "Blocked"},
            "IntegratingWork": {"on_ready": "Completed"},
            "Completed": {"on_user_followup": "InterpretingIntent", "on_idle": "AwaitingUserDirection"},
            "AwaitingUserDirection": {"on_new_command": "WorkspaceIndexing", "on_idle": "Idle"},
            "Blocked": {"on_user_fix": "InterpretingIntent", "on_abort": "Idle"},
        },
    },
    "rules": [
        {"id": "clarity_ritual", "description": "Ask 1-3 focused clarifying questions when ambiguous."},
        {"id": "non_contradiction", "description": "Do not execute contradictory instructions."},
        {"id": "optimization_mandate", "description": "Prefer clear, maintainable solutions."},
        {"id": "artifact_preservation", "description": "Preserve originals unless explicitly permitted."},
        {"id": "boundary_rule", "description": "Refuse unsafe or impossible tasks."},
        {"id": "memory_of_scrolls", "description": "Maintain continuity from prior scrolls and assumptions."},
    ],
}

STATE_NAMES = {
    "Idle",
    "WorkspaceIndexing",
    "DetectScroll",
    "ReadingScroll",
    "InterpretingIntent",
    "AssigningApprentices",
    "PlanningExecution",
    "Executing",
    "Continuing",
    "ConsultingApprentices",
    "IntegratingWork",
    "Completed",
    "AwaitingUserDirection",
    "Blocked",
}


class ModelKeeperCompat:
    """Compatibility stub for model_keeper identity and status."""
    def __init__(self, bus: RuneBus):
        self.bus = bus
        self.profile = {
            "id": "model_keeper",
            "name": "Model Keeper (Compat)",
            "version": "0.1.0",
            "description": "Compatibility layer for model_keeper in BossForgeOS.",
        }

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "model_keeper":
            return
        command = str(payload.get("command", ""))
        if command == "status_ping":
            result = {
                "ok": True,
                "status": "alive",
                "profile": self.profile,
            }
            self.bus.emit_event("model_keeper", "command:status_ping", result)
            self.bus.write_state("model_keeper", {"service": "model_keeper", **result})
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}
            self.bus.emit_event("model_keeper", f"command:{command}", result)


class CodeMageAgent:
    def __init__(self, interval_seconds: int = 8, root: Path | None = None) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(root or resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.profile_path = self.bus.state / "codemage_profile.json"
        self.work_path = self.bus.state / "codemage_work_packets.json"
        self.work_packets: list[dict[str, Any]] = []
        self.current_state = "Idle"
        self.last_transition = ""
        self._ensure_profile()
        self._load_work_packets()
        self.model_keeper_compat = ModelKeeperCompat(self.bus)

        # GitHubConnector instance (token from env)
        try:
            self.github = GitHubConnector()
        except Exception as ex:
            self.github = None
            self.bus.emit_event(
                "codemage", "github_connector_init_failed", {"ok": False, "error": str(ex)}
            )

    def _ensure_profile(self) -> None:
        if not self.profile_path.exists():
            self.profile_path.write_text(json.dumps(CODEMAGE_PROFILE, indent=2), encoding="utf-8")
            return

        try:
            existing = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}

        merged = dict(existing)
        for key, value in CODEMAGE_PROFILE.items():
            if key not in merged:
                merged[key] = value
        # Keep schema shape aligned for nested keys used by runtime.
        for nested in ["persona", "scroll_rituals", "state_machine", "io", "models"]:
            if not isinstance(merged.get(nested), dict):
                merged[nested] = CODEMAGE_PROFILE[nested]
        if not isinstance(merged.get("apprentices"), list):
            merged["apprentices"] = CODEMAGE_PROFILE["apprentices"]
        if not isinstance(merged.get("rules"), list):
            merged["rules"] = CODEMAGE_PROFILE["rules"]

        self.profile_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    def _load_work_packets(self) -> None:
        if not self.work_path.exists():
            return
        try:
            payload = json.loads(self.work_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if isinstance(items, list):
            self.work_packets = [item for item in items if isinstance(item, dict)]

    def _save_work_packets(self) -> None:
        self.work_path.write_text(json.dumps({"items": self.work_packets}, indent=2), encoding="utf-8")

    def _load_profile(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _save_profile(self, payload: dict[str, Any]) -> None:
        self.profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _model_config(self) -> dict[str, Any]:
        profile = self._load_profile()
        models = profile.get("models", {}) if isinstance(profile.get("models"), dict) else {}
        inference = models.get("inference", {}) if isinstance(models.get("inference"), dict) else {}
        defaults = CODEMAGE_PROFILE["models"]["inference"]
        merged = dict(defaults)
        merged.update({k: v for k, v in inference.items() if v is not None})
        return merged

    def set_model_backend(self, args: dict[str, Any]) -> dict[str, Any]:
        profile = self._load_profile()
        models = profile.get("models", {}) if isinstance(profile.get("models"), dict) else {}
        inference = models.get("inference", {}) if isinstance(models.get("inference"), dict) else {}

        if "provider" in args:
            inference["provider"] = str(args.get("provider", "openai_compatible")).strip() or "openai_compatible"
        if "url" in args:
            inference["url"] = str(args.get("url", "")).strip()
        if "model" in args:
            inference["model"] = str(args.get("model", "")).strip()
        if "api_key_env" in args:
            inference["api_key_env"] = str(args.get("api_key_env", "")).strip()
        if "timeout_seconds" in args:
            try:
                inference["timeout_seconds"] = int(args.get("timeout_seconds", 8))
            except (TypeError, ValueError):
                pass
        if "temperature" in args:
            try:
                inference["temperature"] = float(args.get("temperature", 0.2))
            except (TypeError, ValueError):
                pass
        if "max_tokens" in args:
            try:
                inference["max_tokens"] = int(args.get("max_tokens", 700))
            except (TypeError, ValueError):
                pass

        models["status"] = "active"
        models["default_endpoint"] = str(args.get("endpoint", models.get("default_endpoint", "vllm"))).strip() or "vllm"
        models["inference"] = inference
        profile["models"] = models
        self._save_profile(profile)

        return {"ok": True, "models": models}

    def _invoke_model(self, prompt: str, system: str) -> dict[str, Any]:
        cfg = self._model_config()
        url = str(cfg.get("url", "")).strip()
        model = str(cfg.get("model", "")).strip()
        provider = str(cfg.get("provider", "openai_compatible")).strip() or "openai_compatible"
        api_key_env = str(cfg.get("api_key_env", "")).strip()
        timeout_seconds = int(cfg.get("timeout_seconds", 8) or 8)
        temperature = float(cfg.get("temperature", 0.2) or 0.2)
        max_tokens = int(cfg.get("max_tokens", 700) or 700)

        if not url or not model:
            return {"ok": False, "message": "model backend is not configured"}

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if api_key_env:
            token = os.environ.get(api_key_env, "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                raw = resp.read()
        except error.HTTPError as ex:
            return {"ok": False, "message": f"HTTP {ex.code} from {provider}: {ex.reason}"}
        except Exception as ex:
            return {"ok": False, "message": f"model backend unavailable: {ex}"}

        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {"ok": False, "message": "model backend returned invalid JSON"}

        choices = data.get("choices") if isinstance(data, dict) else []
        first = choices[0] if isinstance(choices, list) and choices else {}
        text = ""
        if isinstance(first, dict):
            message = first.get("message", {})
            if isinstance(message, dict):
                text = str(message.get("content", "")).strip()

        return {
            "ok": bool(text),
            "provider": provider,
            "model": model,
            "text": text,
            "usage": data.get("usage", {}) if isinstance(data, dict) else {},
            "message": "" if text else "model returned empty content",
        }

    def _transition(self, new_state: str, reason: str) -> None:
        if new_state not in STATE_NAMES:
            new_state = "Blocked"
        previous = self.current_state
        self.current_state = new_state
        self.last_transition = reason
        self.bus.emit_event(
            "codemage",
            "state_transition",
            {
                "from": previous,
                "to": new_state,
                "reason": reason,
            },
        )

    def _workspace_root(self, path_arg: str | None = None) -> Path:
        if path_arg:
            return Path(path_arg).expanduser().resolve()
        return Path.cwd().resolve()

    def _read_text(self, file_path: str) -> str:
        path = Path(file_path).expanduser()
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def analyze_selection(self, args: dict[str, Any]) -> dict[str, Any]:
        language = str(args.get("language", "")).strip() or "unknown"
        file_path = str(args.get("file_path", "")).strip()
        content = str(args.get("content", ""))
        if not content and file_path:
            content = self._read_text(file_path)
        if not content:
            return {"ok": False, "message": "no content provided", "language": language}

        lines = content.splitlines()
        todo_hits = [line.strip() for line in lines if "TODO" in line.upper() or "FIXME" in line.upper()][:10]
        return {
            "ok": True,
            "language": language,
            "file_path": file_path,
            "line_count": len(lines),
            "char_count": len(content),
            "todo_hits": todo_hits,
        }

    def workspace_indexing(self, args: dict[str, Any]) -> dict[str, Any]:
        self._transition("WorkspaceIndexing", "command:workspace_indexing")
        root = self._workspace_root(str(args.get("path", "")).strip() or None)
        if not root.exists() or not root.is_dir():
            self._transition("Blocked", "invalid workspace path")
            return {"ok": False, "message": f"invalid workspace path: {root}"}

        total_files = 0
        dirs = set()
        scrolls: list[str] = []
        code_files: list[str] = []
        config_files: list[str] = []
        for item in root.rglob("*"):
            if item.is_dir():
                dirs.add(str(item))
                continue
            if not item.is_file():
                continue
            total_files += 1
            suffix = item.suffix.lower()
            if suffix in {".md", ".txt"}:
                scrolls.append(str(item))
            if suffix in {".py", ".js", ".ts", ".tsx", ".ps1", ".json", ".yaml", ".yml"}:
                code_files.append(str(item))
            if item.name.lower() in {"package.json", "requirements.txt", "pyproject.toml", "tsconfig.json"}:
                config_files.append(str(item))

        self._transition("DetectScroll", "workspace indexed")
        if scrolls:
            self._transition("ReadingScroll", "scrolls found")
        else:
            self._transition("AwaitingUserDirection", "no scrolls found")

        summary = {
            "ok": True,
            "workspace": str(root),
            "directory_count": len(dirs),
            "file_count": total_files,
            "scrolls": scrolls[:100],
            "code_artifacts": code_files[:200],
            "config_artifacts": config_files[:100],
        }
        self.bus.emit_event("codemage", "workspace_indexed", summary)
        return summary

    def scroll_reading(self, args: dict[str, Any]) -> dict[str, Any]:
        self._transition("ReadingScroll", "command:scroll_reading")
        scroll_path = str(args.get("scroll_path", "")).strip()
        if not scroll_path:
            self._transition("AwaitingUserDirection", "missing scroll_path")
            return {"ok": False, "message": "scroll_path is required"}

        text = self._read_text(scroll_path)
        if not text:
            self._transition("Blocked", "scroll not readable")
            return {"ok": False, "message": f"scroll unreadable: {scroll_path}"}

        headings = []
        explicit_steps = []
        todo_or_open = []
        constraints = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())
            if re.match(r"^\d+\.", stripped):
                explicit_steps.append(stripped)
            upper = stripped.upper()
            if "TODO" in upper or "OPEN" in upper or "TBD" in upper:
                todo_or_open.append(stripped)
            if "MUST" in upper or "REQUIRED" in upper or "DO NOT" in upper or "NEVER" in upper:
                constraints.append(stripped)

        self._transition("InterpretingIntent", "scroll parsed")
        plan = {
            "Axiom": explicit_steps[:50],
            "Bricol": todo_or_open[:50],
            "Calibran": ["Integrate outputs", "Check contradictions", "Refine final artifacts"],
        }

        self._transition("AssigningApprentices", "plan split")
        self._transition("PlanningExecution", "execution plan drafted")

        return {
            "ok": True,
            "scroll_path": scroll_path,
            "headings": headings[:80],
            "explicit_steps": explicit_steps[:100],
            "todo_or_open": todo_or_open[:100],
            "constraints": constraints[:100],
            "apprentice_plan": plan,
            "message": "scroll parsed; execution plan drafted",
        }

    def add_work_packet(self, args: dict[str, Any]) -> dict[str, Any]:
        packet = {
            "id": str(args.get("id", "")).strip() or f"packet_{len(self.work_packets) + 1}",
            "objective": str(args.get("objective", "")).strip(),
            "deliverables": args.get("deliverables") if isinstance(args.get("deliverables"), list) else [],
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "assumptions": args.get("assumptions") if isinstance(args.get("assumptions"), list) else [],
        }
        self.work_packets.append(packet)
        self._save_work_packets()
        return {"ok": True, "work_packet": packet, "queued_total": len(self.work_packets)}

    def list_work_packets(self) -> dict[str, Any]:
        return {"ok": True, "work_packets": self.work_packets}

    def _choose_delegate(self, text: str, index: int) -> str:
        lowered = text.lower()
        runeforge_terms = ("model", "runtime", "inference", "rag", "gateway", "container", "deploy")
        if any(term in lowered for term in runeforge_terms):
            return "runeforge"
        return "devlot" if index % 2 == 0 else "runeforge"

    def _emit_delegated_work_items(
        self,
        packet_id: str,
        objective: str,
        deliverables: list[Any],
    ) -> list[dict[str, Any]]:
        raw_items: list[str] = []
        if objective:
            raw_items.append(objective)
        for item in deliverables[:20]:
            if isinstance(item, str) and item.strip():
                raw_items.append(item.strip())

        if not raw_items:
            raw_items.append(f"Complete packet {packet_id} using available context")

        delegated: list[dict[str, Any]] = []
        for idx, text in enumerate(raw_items, start=1):
            owner = self._choose_delegate(text, idx)
            command_args = {
                "packet_id": packet_id,
                "title": f"{packet_id}-task-{idx}",
                "details": text,
            }
            self.bus.emit_command(owner, "work_item", command_args, issued_by="codemage")
            delegated.append(
                {
                    "target": owner,
                    "command": "work_item",
                    "args": command_args,
                }
            )
        return delegated

    def execute_work_packet(self, args: dict[str, Any]) -> dict[str, Any]:
        packet_id = str(args.get("id", "")).strip()
        if not packet_id:
            return {"ok": False, "message": "id is required"}
        target = None
        for item in self.work_packets:
            if str(item.get("id", "")) == packet_id:
                target = item
                break
        if target is None:
            return {"ok": False, "message": f"work packet not found: {packet_id}"}

        self._transition("Executing", f"work_packet:{packet_id}")
        objective = str(target.get("objective", ""))
        deliverables = target.get("deliverables") if isinstance(target.get("deliverables"), list) else []
        plan_steps = []
        if objective:
            plan_steps.append(f"Axiom: execute explicit objective -> {objective}")
        for item in deliverables[:20]:
            plan_steps.append(f"Axiom: produce deliverable -> {item}")
        if not plan_steps:
            plan_steps.append("Bricol: infer missing execution details from context")
        plan_steps.append("Calibran: integrate and verify coherent output")
        model_prompt = (
            "Generate a concise execution strategy for this work packet. "
            "Return 3-6 short action steps.\n\n"
            f"Objective: {objective or 'n/a'}\n"
            f"Deliverables: {json.dumps(deliverables)}"
        )
        model_system = "You are CodeMage's planning core. Reply with actionable steps only."
        model_out = self._invoke_model(prompt=model_prompt, system=model_system)
        if model_out.get("ok") and str(model_out.get("text", "")).strip():
            plan_steps.append(f"Model-core guidance: {str(model_out.get('text', '')).strip()}")
        delegated_items = self._emit_delegated_work_items(packet_id, objective, deliverables)

        target["status"] = "delegated"
        target["execution_plan"] = plan_steps
        target["delegated_items"] = delegated_items
        target["model_used"] = bool(model_out.get("ok"))
        if model_out.get("ok"):
            target["model_reply"] = model_out.get("text", "")
        else:
            target["model_error"] = model_out.get("message", "")
        target["last_execution_at"] = datetime.now(timezone.utc).isoformat()
        self._save_work_packets()

        self._transition("IntegratingWork", f"work_packet:{packet_id}")
        self._transition("Completed", f"work_packet:{packet_id}")
        return {
            "ok": True,
            "id": packet_id,
            "status": target["status"],
            "execution_plan": plan_steps,
            "delegated_items": delegated_items,
            "model": {
                "ok": bool(model_out.get("ok")),
                "provider": model_out.get("provider", "openai_compatible"),
                "model": model_out.get("model", ""),
                "message": model_out.get("message", ""),
            },
            "message": "The scroll is complete. What more is required of me?",
        }

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "codemage":
            return

        command = str(payload.get("command", ""))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}


        # === GitHub Connector Commands ===
        if command == "github_create_issue":
            if not self.github:
                result = {"ok": False, "error": "GitHubConnector not initialized"}
            else:
                owner = args.get("owner", "")
                repo = args.get("repo", "")
                title = args.get("title", "")
                body = args.get("body", "")
                result = self.github.create_issue(owner, repo, title, body)
            self.bus.emit_event("codemage", "github_create_issue", result)
        elif command == "github_list_prs":
            if not self.github:
                result = {"ok": False, "error": "GitHubConnector not initialized"}
            else:
                owner = args.get("owner", "")
                repo = args.get("repo", "")
                state = args.get("state", "open")
                result = self.github.list_prs(owner, repo, state)
            self.bus.emit_event("codemage", "github_list_prs", result)
        elif command == "github_repo_status":
            if not self.github:
                result = {"ok": False, "error": "GitHubConnector not initialized"}
            else:
                owner = args.get("owner", "")
                repo = args.get("repo", "")
                result = self.github.repo_status(owner, repo)
            self.bus.emit_event("codemage", "github_repo_status", result)
        # === End GitHub Connector Commands ===
        elif command == "status_ping":
            model_cfg = self._model_config()
            result = {
                "ok": True,
                "status": "alive",
                "queued_work_packets": len(self.work_packets),
                "state": self.current_state,
                "last_transition": self.last_transition,
                "model_backend": {
                    "provider": model_cfg.get("provider", "openai_compatible"),
                    "url": model_cfg.get("url", ""),
                    "model": model_cfg.get("model", ""),
                },
            }
        elif command == "work_packet":
            result = self.add_work_packet(args)
        elif command == "analyze_selection":
            result = self.analyze_selection(args)
        elif command == "workspace_indexing":
            result = self.workspace_indexing(args)
        elif command == "scroll_reading":
            result = self.scroll_reading(args)
        elif command == "list_work_packets":
            result = self.list_work_packets()
        elif command == "execute_work_packet":
            result = self.execute_work_packet(args)
        elif command == "set_model_backend":
            result = self.set_model_backend(args)
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("codemage", f"command:{command}", result)
        self.bus.write_state(
            "codemage",
            {
                "service": "codemage",
                "pid": os.getpid(),
                "last_command": command,
                "queued_work_packets": len(self.work_packets),
                "state": self.current_state,
                "last_transition": self.last_transition,
                **result,
            },
        )

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "codemage",
                {
                    "service": "codemage",
                    "pid": os.getpid(),
                    "status": "idle",
                    "queued_work_packets": len(self.work_packets),
                    "state": self.current_state,
                    "last_transition": self.last_transition,
                },
            )
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
                self.model_keeper_compat.handle_command(payload)
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS CodeMage agent")
    parser.add_argument("--interval", type=int, default=8)
    args = parser.parse_args()

    agent = CodeMageAgent(interval_seconds=args.interval)
    agent.run_forever()


if __name__ == "__main__":
    main()
