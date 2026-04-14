import argparse
import json
import os
import re
import signal
import subprocess
import sys
import pathlib

# === Path Resolver for Bundled/Source Modes ===
def get_project_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parent.parent.parent

PROJECT_ROOT = get_project_root()
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.agent_registry import register_agent
from core.prime_agent import PrimeAgent


RUNEFORGE_PROFILE: dict[str, Any] = {
    "id": "runeforge",
    "name": "Runeforge, First Mind of the Forge",
    "version": "1.0.0",
    "description": "Model/runtime infrastructure steward for BossForge workloads.",
    "llm_router": {
        "enabled": True,
        "provider": "openai_compatible",
        "url": "http://127.0.0.1:8000/v1/chat/completions",
        "model": "runeforge_Core-7b",
        "api_key_env": "",
        "timeout_seconds": 8,
        "temperature": 0.0,
        "max_tokens": 350,
    },
}


class RuneforgeAgent(PrimeAgent):
    def __init__(self, interval_seconds: int = 15, root: Path | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interval_seconds = interval_seconds
        self.root = root or resolve_root_from_env()
        self.bus = RuneBus(self.root)
        self.seen_commands: set[str] = set()
        self.profile_path = self.bus.state / "runeforge_profile.json"
        self.tasks_path = self.bus.state / "runeforge_tasks.json"
        self.voice_aliases_path = self.bus.state / "runeforge_voice_aliases.json"
        self.pending_approval_path = self.bus.state / "runeforge_pending_approval.json"
        self.tasks: list[dict] = []
        self._sigil_registry: dict = {}
        self._system_laws: dict = {}
        self._fate_workflows: list = []
        self._banished_agents: set = set()
        self.os_edition_dir = self.root / "Runeforge OS Edition"
        self._ensure_profile()
        self._ensure_voice_aliases()
        self._load_tasks()

    # === Persistence helpers ===
    def _prime_state_path(self, key: str) -> Path:
        return self.bus.state / f"runeforge_{key}.json"

    def _save_prime_state(self, key: str, value: Any):
        path = self._prime_state_path(key)
        try:
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_prime_state(self, key: str, default: Any):
        path = self._prime_state_path(key)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    # Override setters to persist state
    def sigil_synthesis(self, sigil_name: str, sigil_callable: Any = None, **kwargs):
        if not sigil_name:
            return {"ok": False, "message": "Sigil name required."}
        if sigil_callable:
            self._sigil_registry[sigil_name] = sigil_callable
            self._save_prime_state("sigils", list(self._sigil_registry.keys()))
            return {"ok": True, "message": f"Sigil '{sigil_name}' registered."}
        # List sigils
        return {"ok": True, "sigils": list(self._sigil_registry.keys())}

    def system_scribe(self, law: str = None, value: Any = None, **kwargs):
        if law and value is not None:
            self._system_laws[law] = value
            self._save_prime_state("laws", self._system_laws)
            return {"ok": True, "message": f"Law '{law}' set to {value}."}
        elif law:
            return {"ok": True, "law": law, "value": self._system_laws.get(law)}
        # List all laws
        return {"ok": True, "laws": dict(self._system_laws)}

    def fate_threading(self, workflow: dict = None, **kwargs):
        if workflow:
            self._fate_workflows.append(workflow)
            self._save_prime_state("workflows", self._fate_workflows)
            return {"ok": True, "message": "Workflow added.", "workflow": workflow}
        # List all workflows
        return {"ok": True, "workflows": list(self._fate_workflows)}

    # === Prime ability command routing ===
    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "runeforge":
            return

        command = str(payload.get("command", ""))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}

        # Prime ability commands
        if command == "reality_weaving":
            result = self.reality_weaving(**args)
        elif command == "sigil_synthesis":
            result = self.sigil_synthesis(**args)
        elif command == "system_scribe":
            result = self.system_scribe(**args)
        elif command == "fate_threading":
            result = self.fate_threading(**args)
        elif command == "sanctum_of_invocation":
            result = self.sanctum_of_invocation(**args)
        # ...existing code...
        elif command == "status_ping":
            result = {"ok": True, "status": "alive", "queued_tasks": len(self.tasks)}
        elif command == "work_packet":
            result = self.add_work_packet(args)
        elif command == "work_item":
            result = self.add_work_item(args)
        elif command == "list_tasks":
            result = self.list_tasks()
        elif command == "run_os_observation":
            result = self.run_os_observation()
        elif command == "run_os_action":
            result = self.run_os_action(args)
        elif command == "list_os_actions":
            result = self.list_os_actions()
        elif command == "voice_command":
            result = self.run_voice_text(args)
        elif command == "voice_listen":
            result = self.listen_voice_once(args)
        elif command == "accept_sentinel_recommendations":
            result = self.accept_sentinel_recommendations(args)
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("runeforge", f"command:{command}", result)
        self.bus.write_state(
            "runeforge",
            {
                "service": "runeforge",
                "pid": os.getpid(),
                "last_command": command,
                "queued_tasks": len(self.tasks),
                **result,
            },
        )



    def reality_weaving(self, action: str, agent_id: str = None, **kwargs):
        """Dynamically reconfigure the agent ecosystem: spawn, merge, retire, or alter agents."""
        from core.agent_registry import registry
        if action == "banish" and agent_id:
            self._banished_agents.add(agent_id)
            registry.unregister_agent(agent_id)
            return {"ok": True, "message": f"Agent {agent_id} banished."}
        elif action == "spawn" and agent_id:
            # In real system, would launch a new agent process/module
            registry.register_agent(agent_id, {"id": agent_id, "name": agent_id.title(), "description": "Spawned by Runeforge."})
            return {"ok": True, "message": f"Agent {agent_id} spawned."}
        elif action == "update_profile" and agent_id and "profile" in kwargs:
            registry.register_agent(agent_id, kwargs["profile"])
            return {"ok": True, "message": f"Agent {agent_id} profile updated."}
        return {"ok": False, "message": "Unknown or incomplete reality weaving action."}

    def sanctum_of_invocation(self, action: str, agent_id: str = None, **kwargs):
        """Privileged interface for summoning/banishing agents and managing registry."""
        # For now, just call reality_weaving
        return self.reality_weaving(action, agent_id, **kwargs)


    def _command_processor_path(self) -> Path:
        return self.os_edition_dir / "command_processor.py"

    def _voice_dictation_path(self) -> Path:
        return self.os_edition_dir / "audio_dictation.py"

    def _normalize_phrase(self, phrase: str) -> str:
        cleaned = re.sub(r"\s+", " ", phrase.strip().lower())
        return cleaned.strip(" ,:-|")

    def _known_agent_monikers(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        aliases = self._load_voice_aliases()
        for agent_id in self._discover_agents():
            aid = self._normalize_phrase(agent_id.replace(" ", "_"))
            if not aid:
                continue
            mapping[self._normalize_phrase(agent_id)] = aid
            mapping[self._normalize_phrase(agent_id.replace("_", " "))] = aid
            for alias in aliases.get(aid, []):
                # Agent aliases can be used as monikers, but only for task delegation.
                mapping[self._normalize_phrase(alias)] = aid
        return mapping

    def _strip_activation_prefix(self, text: str) -> tuple[bool, str]:
        normalized = self._normalize_phrase(text)
        for phrase in ("runeforge", "runforge"):
            if normalized.startswith(phrase + " "):
                stripped = normalized[len(phrase) + 1 :].strip()
                return bool(stripped), stripped
            if normalized.startswith(phrase + ","):
                stripped = normalized[len(phrase) + 1 :].strip()
                return bool(stripped), stripped
            if normalized == phrase:
                return False, ""
        return False, normalized

    def _classify_voice_moniker(self, text: str) -> dict[str, Any]:
        normalized = self._normalize_phrase(text)
        if not normalized:
            return {"type": "none", "agent": "", "content": ""}

        activated, cleaned = self._strip_activation_prefix(normalized)
        if activated:
            return {"type": "runeforge", "agent": "runeforge", "content": cleaned}

        monikers = self._known_agent_monikers()
        for moniker, agent in monikers.items():
            if normalized == moniker:
                return {"type": "agent", "agent": agent, "content": ""}
            if normalized.startswith(moniker + " "):
                return {
                    "type": "agent",
                    "agent": agent,
                    "content": normalized[len(moniker) + 1 :].strip(),
                }
            if normalized.startswith(moniker + ","):
                return {
                    "type": "agent",
                    "agent": agent,
                    "content": normalized[len(moniker) + 1 :].strip(),
                }

        return {"type": "none", "agent": "", "content": normalized}

    def _assign_voice_task_to_agent(self, agent: str, details: str, spoken_text: str) -> dict[str, Any]:
        task_details = details.strip()
        if not task_details:
            return {
                "ok": False,
                "spoken_text": spoken_text,
                "voice_action": "agent_task_assignment",
                "message": "Agent moniker detected but no task text was provided",
                "example": f"{agent} analyze the login errors and report root cause",
            }

        title = task_details[:72]
        if len(task_details) > 72:
            title = title.rstrip() + "..."

        work_item_args = {
            "packet_id": "voice_delegation",
            "title": title,
            "details": task_details,
            "source": "voice",
            "assigned_by": "runeforge",
            "spoken_text": spoken_text,
        }
        self.bus.emit_command(agent, "work_item", work_item_args, issued_by="voice")
        self.bus.emit_event(
            "runeforge",
            "voice_task_assigned",
            {
                "agent": agent,
                "details": task_details,
                "spoken_text": spoken_text,
                "policy": "agent_moniker_task_only",
            },
        )
        return {
            "ok": True,
            "spoken_text": spoken_text,
            "voice_action": "agent_task_assignment",
            "policy": "agent_moniker_task_only",
            "result": {
                "agent": agent,
                "command": "work_item",
                "args": work_item_args,
                "message": "Task dispatched to agent queue",
            },
        }

    def _discover_agents(self) -> list[str]:
        discovered = {"runeforge", "codemage", "devlot", "archivist", "model_gateway", "security_sentinel"}
        for path in self.bus.state.glob("*_profile.json"):
            agent_id = path.stem.replace("_profile", "").strip().lower()
            if agent_id:
                discovered.add(agent_id)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("id"), str):
                discovered.add(str(payload.get("id")).strip().lower())
        return sorted(discovered)

    def _load_voice_aliases(self) -> dict[str, list[str]]:
        if not self.voice_aliases_path.exists():
            return {}
        try:
            payload = json.loads(self.voice_aliases_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        raw = payload.get("aliases") if isinstance(payload, dict) else None
        if not isinstance(raw, dict):
            return {}
        out: dict[str, list[str]] = {}
        for agent, aliases in raw.items():
            if not isinstance(agent, str) or not isinstance(aliases, list):
                continue
            normalized = []
            for value in aliases:
                if isinstance(value, str) and value.strip():
                    normalized.append(self._normalize_phrase(value))
            if normalized:
                out[agent.lower().strip()] = sorted(set(normalized))
        return out

    def _save_voice_aliases(self, aliases: dict[str, list[str]]) -> None:
        payload = {
            "version": "1.0",
            "aliases": aliases,
        }
        self.voice_aliases_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _ensure_voice_aliases(self) -> None:
        aliases = self._load_voice_aliases()
        changed = False
        for agent_id in self._discover_agents():
            existing = aliases.get(agent_id, [])
            desired = set(existing)
            desired.add(self._normalize_phrase(agent_id))
            desired.add(self._normalize_phrase(agent_id.replace("_", " ")))
            merged = sorted(v for v in desired if v)
            if merged != existing:
                aliases[agent_id] = merged
                changed = True
        if changed or not self.voice_aliases_path.exists():
            self._save_voice_aliases(aliases)

    def _register_agent_alias(self, agent_id: str, alias: str) -> dict[str, Any]:
        agent = self._normalize_phrase(agent_id.replace(" ", "_"))
        phrase = self._normalize_phrase(alias)
        if not agent or not phrase:
            return {"ok": False, "message": "agent_id and alias are required"}
        aliases = self._load_voice_aliases()
        current = set(aliases.get(agent, []))
        current.add(phrase)
        aliases[agent] = sorted(current)
        self._save_voice_aliases(aliases)
        return {"ok": True, "agent": agent, "alias": phrase, "aliases": aliases.get(agent, [])}

    def _load_profile(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _save_profile(self, payload: dict[str, Any]) -> None:
        self.profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _llm_router_config(self) -> dict[str, Any]:
        profile = self._load_profile()
        raw = profile.get("llm_router", {}) if isinstance(profile.get("llm_router"), dict) else {}
        cfg = dict(RUNEFORGE_PROFILE.get("llm_router", {}))
        cfg.update({k: v for k, v in raw.items() if v is not None})
        return cfg

    def _supported_action_types(self) -> list[str]:
        schema_path = self.os_edition_dir / "action_schema.json"
        if not schema_path.exists():
            return []
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        values = payload.get("supported_action_types", []) if isinstance(payload, dict) else []
        return [str(v).strip() for v in values if isinstance(v, str) and str(v).strip()]

    def _high_risk_action_types(self) -> set[str]:
        schema_path = self.os_edition_dir / "action_schema.json"
        if not schema_path.exists():
            return set()
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        values = payload.get("high_risk_action_types", []) if isinstance(payload, dict) else []
        return {str(v).strip() for v in values if isinstance(v, str) and str(v).strip()}

    def _confirmation_only_action_types(self) -> set[str]:
        # Confirmation is required, but command code is not.
        return {"close_app", "set_volume"}

    def _command_code_required_action_types(self) -> set[str]:
        configured = set(self._high_risk_action_types())
        # Explicit carve-out: close_app only needs confirmation, not command code.
        configured.discard("close_app")
        # Volume changes are confirmation-level, not command-code level.
        configured.discard("set_volume")
        # Secret/privileged scopes should require command code.
        configured.update({
            "grant_permission",
            "revoke_permission",
            "delete_file",
            "move_file",
            "copy_file",
            "registry_edit",
        })
        return configured

    def _voice_confidence_threshold(self) -> float:
        return 0.65

    def _needs_clarification(self, confidence: float | None) -> bool:
        if confidence is None:
            return False
        return float(confidence) < self._voice_confidence_threshold()

    def _invoke_llm_router(self, spoken_text: str) -> dict[str, Any]:
        cfg = self._llm_router_config()
        if not bool(cfg.get("enabled", True)):
            return {"ok": False, "message": "llm_router disabled"}

        url = str(cfg.get("url", "")).strip()
        model = str(cfg.get("model", "")).strip()
        provider = str(cfg.get("provider", "openai_compatible")).strip() or "openai_compatible"
        api_key_env = str(cfg.get("api_key_env", "")).strip()
        timeout_seconds = int(cfg.get("timeout_seconds", 8) or 8)
        temperature = float(cfg.get("temperature", 0.0) or 0.0)
        max_tokens = int(cfg.get("max_tokens", 350) or 350)
        if not url or not model:
            return {"ok": False, "message": "llm_router endpoint not configured"}

        known_agents = self._discover_agents()
        aliases = self._load_voice_aliases()
        supported_actions = self._supported_action_types()

        system = (
            "You are a strict intent router for BossForge Runeforge voice commands. "
            "Return ONLY one JSON object with keys: intent_type, agent, alias, action, confidence, reason. "
            "intent_type must be one of: agent_ping, register_alias, os_action, none. "
            "agent is lowercase snake_case or empty. alias is string or empty. "
            "action is an object with action_type and params, or null. "
            "Do not include markdown."
        )
        prompt = json.dumps(
            {
                "spoken_text": spoken_text,
                "known_agents": known_agents,
                "voice_aliases": aliases,
                "supported_action_types": supported_actions,
            },
            ensure_ascii=True,
        )

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
            return {"ok": False, "message": f"llm_router unavailable: {ex}"}

        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {"ok": False, "message": "llm_router returned invalid JSON"}

        choices = data.get("choices") if isinstance(data, dict) else []
        first = choices[0] if isinstance(choices, list) and choices else {}
        text = ""
        if isinstance(first, dict):
            message = first.get("message", {})
            if isinstance(message, dict):
                text = str(message.get("content", "")).strip()
        if not text:
            return {"ok": False, "message": "llm_router returned empty content"}

        try:
            routed = json.loads(text)
        except json.JSONDecodeError:
            return {"ok": False, "message": "llm_router content was not JSON", "raw": text}
        if not isinstance(routed, dict):
            return {"ok": False, "message": "llm_router output is not an object", "raw": text}
        return {"ok": True, "route": routed, "provider": provider, "model": model}

    def _try_route_with_llm(self, spoken_text: str, command_code: str = "") -> dict[str, Any] | None:
        routed = self._invoke_llm_router(spoken_text)
        if not routed.get("ok"):
            return None

        route = routed.get("route") if isinstance(routed.get("route"), dict) else {}
        intent_type = str(route.get("intent_type", "none")).strip().lower()
        confidence_raw = route.get("confidence")
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else None

        if self._needs_clarification(confidence):
            msg = "I heard your command, but confidence is low. Please repeat with more detail."
            self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="warning")
            return {
                "ok": False,
                "spoken_text": spoken_text,
                "voice_action": "clarification_required",
                "confidence": confidence,
                "message": msg,
            }

        if intent_type == "none":
            return None

        if intent_type == "agent_ping":
            agent = self._normalize_phrase(str(route.get("agent", "")).replace(" ", "_"))
            if not agent:
                return None
            result = self._voice_ping_agent(agent)
            return {
                "ok": bool(result.get("ok")),
                "spoken_text": spoken_text,
                "voice_action": "agent_ping",
                "via": "llm_router",
                "llm_route": route,
                "result": result,
            }

        if intent_type == "register_alias":
            agent = self._normalize_phrase(str(route.get("agent", "")).replace(" ", "_"))
            alias = str(route.get("alias", "")).strip()
            if not agent or not alias:
                return None
            result = self._register_agent_alias(agent, alias)
            return {
                "ok": bool(result.get("ok")),
                "spoken_text": spoken_text,
                "voice_action": "register_agent_alias",
                "via": "llm_router",
                "llm_route": route,
                "result": result,
            }

        if intent_type == "os_action":
            action = route.get("action")
            if not isinstance(action, dict):
                return None
            action_type = str(action.get("action_type", "")).strip()
            if action_type and action_type not in set(self._supported_action_types()):
                return None
            if action_type in self._high_risk_action_types():
                approval = self.request_os_action_approval({"action": action, "spoken_text": spoken_text, "source": "voice_llm"})
                return {
                    "ok": bool(approval.get("ok")),
                    "spoken_text": spoken_text,
                    "voice_action": "request_os_action_approval",
                    "confidence": confidence,
                    "via": "llm_router",
                    "llm_route": route,
                    "result": approval,
                }
            cli_args = ["--action-json", json.dumps(action), "--agent", "runeforge"]
            if command_code:
                cli_args.extend(["--command-code", command_code])
            os_result = self._run_os_command_processor(cli_args, timeout_seconds=180)
            return {
                "ok": bool(os_result.get("ok")),
                "spoken_text": spoken_text,
                "voice_action": "os_action",
                "confidence": confidence,
                "via": "llm_router",
                "llm_route": route,
                "parsed_action": action,
                "result": os_result.get("parsed") if isinstance(os_result.get("parsed"), dict) else None,
                "command_processor": {
                    "returncode": os_result.get("returncode"),
                    "stderr": os_result.get("stderr", ""),
                    "stdout": os_result.get("stdout", ""),
                },
            }

        return None

    def _resolve_agent_from_text(self, text: str) -> str | None:
        cleaned = self._normalize_phrase(text)
        if not cleaned:
            return None

        for suffix in (" talk to me", " ping", " wake up", " status"):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                break

        aliases = self._load_voice_aliases()
        for agent, values in aliases.items():
            for alias in values:
                if cleaned == alias:
                    return agent
        return None

    def _voice_ping_agent(self, agent: str) -> dict[str, Any]:
        self.bus.emit_command(agent, "status_ping", {}, issued_by="voice")
        self.bus.emit_event(
            agent,
            "voice_ping",
            {
                "message": f"{agent.replace('_', ' ').title()} awakened by voice command.",
                "via": "runeforge_voice_router",
            },
        )
        return {"ok": True, "agent": agent, "message": "voice ping dispatched"}

    def _capture_spoken_text_once(self) -> dict[str, Any]:
        result = self._run_voice_dictation(["--capture-only"], timeout_seconds=180)
        parsed = result.get("parsed") if isinstance(result.get("parsed"), dict) else {}
        spoken = str(parsed.get("spoken_text", "")).strip() if isinstance(parsed, dict) else ""
        if not result.get("ok") or not spoken:
            return {
                "ok": False,
                "message": "failed to capture spoken text",
                "voice_script": {
                    "returncode": result.get("returncode"),
                    "stderr": result.get("stderr", ""),
                    "stdout": result.get("stdout", ""),
                },
            }
        return {"ok": True, "spoken_text": spoken}

    def _execute_voice_text(self, spoken_text: str, command_code: str = "") -> dict[str, Any]:
        text = str(spoken_text or "").strip()
        if not text:
            return {"ok": False, "message": "empty spoken text"}

        moniker = self._classify_voice_moniker(text)
        moniker_type = str(moniker.get("type", "none"))
        if moniker_type == "agent":
            return self._assign_voice_task_to_agent(
                agent=str(moniker.get("agent", "")).strip(),
                details=str(moniker.get("content", "")).strip(),
                spoken_text=text,
            )

        if moniker_type != "runeforge":
            return {
                "ok": False,
                "spoken_text": text,
                "message": "Missing activation moniker",
                "activation_phrases": ["Runeforge", "runforge", "<agent_name> (task assignment only)"],
                "example": "Runeforge open steam OR codemage refactor the login flow",
            }
        cleaned = str(moniker.get("content", "")).strip()

        if "sentinel" in cleaned and ("plan" in cleaned or "recommendation" in cleaned) and any(
            token in cleaned for token in ["review", "seek", "show", "request", "propose"]
        ):
            requested_pids = [int(value) for value in re.findall(r"\b\d+\b", cleaned)]
            requested = self.request_sentinel_plan_approval({"accept_all": not bool(requested_pids), "pids": requested_pids})
            return {
                "ok": bool(requested.get("ok")),
                "spoken_text": text,
                "voice_action": "request_sentinel_plan_approval",
                "result": requested,
            }

        pending = self._load_pending_approval()
        pending_type = str(pending.get("type", "")).strip().lower()
        if pending_type in {"sentinel_plan", "os_action"}:
            if self._is_affirmative_phrase(cleaned):
                code = self._extract_command_code(cleaned)
                result = self.respond_pending_approval({"approved": True, "source": "voice", "spoken_text": text, "command_code": code})
                return {
                    "ok": bool(result.get("ok")),
                    "spoken_text": text,
                    "voice_action": "approve_pending_action",
                    "result": result,
                }
            if self._is_negative_phrase(cleaned):
                result = self.respond_pending_approval({"approved": False, "source": "voice", "spoken_text": text})
                return {
                    "ok": bool(result.get("ok")),
                    "spoken_text": text,
                    "voice_action": "reject_pending_action",
                    "result": result,
                }
            if pending_type == "os_action":
                code = self._extract_command_code(cleaned)
                if code:
                    result = self.respond_pending_approval({"approved": True, "source": "voice", "spoken_text": text, "command_code": code})
                    return {
                        "ok": bool(result.get("ok")),
                        "spoken_text": text,
                        "voice_action": "approve_pending_action",
                        "result": result,
                    }

        # Voice registration command: "BossForge register voice alias <alias> to agent <id>"
        match = re.match(r"^(register|assign) (voice )?(alias|command) (.+?) (to|for) agent ([a-z0-9_\- ]+)$", cleaned)
        if match:
            alias = match.group(4).strip().strip('"')
            agent_id = match.group(6).strip().replace(" ", "_")
            return {
                "ok": True,
                "spoken_text": text,
                "voice_action": "register_agent_alias",
                "result": self._register_agent_alias(agent_id, alias),
            }

        # Mic-recorded alias flow: "BossForge record alias for agent <id>"
        record_match = re.match(r"^record (voice )?(alias|command) (for|to) agent ([a-z0-9_\- ]+)$", cleaned)
        if record_match:
            agent_id = record_match.group(4).strip().replace(" ", "_")
            captured = self._capture_spoken_text_once()
            if not captured.get("ok"):
                return {"ok": False, "spoken_text": text, "voice_action": "record_agent_alias", "result": captured}
            alias_phrase = str(captured.get("spoken_text", "")).strip()
            reg = self._register_agent_alias(agent_id, alias_phrase)
            return {
                "ok": bool(reg.get("ok")),
                "spoken_text": text,
                "voice_action": "record_agent_alias",
                "recorded_alias": alias_phrase,
                "result": reg,
            }

        # Direct agent wake command: "codemage" / "runeforge talk to me"
        target = self._resolve_agent_from_text(cleaned)
        if target:
            ping_result = self._voice_ping_agent(target)
            return {
                "ok": bool(ping_result.get("ok")),
                "spoken_text": text,
                "voice_action": "agent_ping",
                "result": ping_result,
            }

        if cleaned.startswith("accept sentinel recommendation") or cleaned.startswith("accept sentinel recommendations"):
            mentioned_pids = [int(value) for value in re.findall(r"\b\d+\b", cleaned)]
            accepted = self.request_sentinel_plan_approval({"accept_all": not bool(mentioned_pids), "pids": mentioned_pids})
            return {
                "ok": bool(accepted.get("ok")),
                "spoken_text": text,
                "voice_action": "request_sentinel_plan_approval",
                "result": accepted,
            }

        # LLM router attempt for fuzzy/complex commands.
        llm_route = self._try_route_with_llm(cleaned, command_code=command_code)
        if llm_route is not None:
            return llm_route

        # Fallback to OS voice command parsing.
        parse = self._run_voice_dictation(["--text", text], timeout_seconds=120)
        parsed = parse.get("parsed") if isinstance(parse.get("parsed"), dict) else None
        if not parsed or not parsed.get("ok"):
            return {
                "ok": False,
                "spoken_text": text,
                "voice_action": "unrecognized",
                "voice_parser": {
                    "returncode": parse.get("returncode"),
                    "stderr": parse.get("stderr", ""),
                    "stdout": parse.get("stdout", ""),
                    "parsed": parsed,
                },
            }

        action = parsed.get("action") if isinstance(parsed, dict) else None
        if not isinstance(action, dict):
            return {"ok": False, "spoken_text": text, "message": "voice parser did not return an action"}

        confidence_raw = parsed.get("confidence") if isinstance(parsed, dict) else None
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else None
        if self._needs_clarification(confidence):
            msg = "I am not fully confident about that command. Please repeat it with more detail."
            self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="warning")
            return {
                "ok": False,
                "spoken_text": text,
                "voice_action": "clarification_required",
                "confidence": confidence,
                "message": msg,
            }

        action_type = str(action.get("action_type", "")).strip()
        if action_type in self._high_risk_action_types():
            approval = self.request_os_action_approval({"action": action, "spoken_text": text, "source": "voice_parser"})
            return {
                "ok": bool(approval.get("ok")),
                "spoken_text": text,
                "voice_action": "request_os_action_approval",
                "confidence": confidence,
                "result": approval,
            }

        cli_args = ["--action-json", json.dumps(action), "--agent", "runeforge"]
        if command_code:
            cli_args.extend(["--command-code", command_code])
        os_result = self._run_os_command_processor(cli_args, timeout_seconds=180)

        return {
            "ok": bool(os_result.get("ok")),
            "spoken_text": text,
            "voice_action": "os_action",
            "confidence": confidence,
            "parsed_action": action,
            "result": os_result.get("parsed") if isinstance(os_result.get("parsed"), dict) else None,
            "command_processor": {
                "returncode": os_result.get("returncode"),
                "stderr": os_result.get("stderr", ""),
                "stdout": os_result.get("stdout", ""),
            },
        }

    def _run_os_command_processor(self, args: list[str], timeout_seconds: int = 120) -> dict[str, Any]:
        command_processor = self._command_processor_path()
        if not command_processor.exists():
            return {"ok": False, "message": f"command processor not found: {command_processor}"}

        try:
            proc = subprocess.run(
                [sys.executable, str(command_processor), *args],
                cwd=str(self.os_edition_dir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except Exception as ex:
            return {"ok": False, "message": str(ex)}

        payload: dict[str, Any] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

        for line in reversed(payload["stdout"].splitlines()):
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    payload["parsed"] = parsed
                    break
            except json.JSONDecodeError:
                continue
        return payload

    def _system_memory_available_mb(self) -> int | None:
        try:
            import psutil  # type: ignore

            return int((psutil.virtual_memory().available or 0) / (1024 * 1024))
        except Exception:
            return None

    def _load_pending_approval(self) -> dict[str, Any]:
        if not self.pending_approval_path.exists():
            return {}
        try:
            payload = json.loads(self.pending_approval_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_pending_approval(self, payload: dict[str, Any]) -> None:
        self.pending_approval_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _clear_pending_approval(self) -> None:
        try:
            self.pending_approval_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _is_affirmative_phrase(self, text: str) -> bool:
        cleaned = self._normalize_phrase(text)
        if cleaned in {"yes", "yep", "yeah", "approve", "approved", "agree", "accepted", "accept", "do it", "proceed", "confirm"}:
            return True
        return "approve sentinel" in cleaned or "accept sentinel" in cleaned or "agree with sentinel" in cleaned

    def _is_negative_phrase(self, text: str) -> bool:
        cleaned = self._normalize_phrase(text)
        if cleaned in {"no", "nope", "deny", "decline", "reject", "cancel", "stop"}:
            return True
        return "reject sentinel" in cleaned or "decline sentinel" in cleaned or "cancel sentinel" in cleaned

    def _extract_command_code(self, text: str) -> str:
        cleaned = self._normalize_phrase(text)
        match = re.search(r"(?:command\s+code|code)\s+([a-z0-9\-]{3,64})", cleaned)
        if not match:
            return ""
        return str(match.group(1)).strip()

    def request_os_action_approval(self, args: dict[str, Any]) -> dict[str, Any]:
        action = args.get("action") if isinstance(args.get("action"), dict) else None
        if not action:
            return {"ok": False, "message": "action is required"}
        action_type = str(action.get("action_type", "")).strip()
        if not action_type:
            return {"ok": False, "message": "action_type is required"}

        requires_command_code = bool(args.get("requires_command_code", action_type in self._command_code_required_action_types()))
        pending = {
            "type": "os_action",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "spoken_text": str(args.get("spoken_text", "")).strip(),
            "source": str(args.get("source", "voice")).strip() or "voice",
            "requires_command_code": requires_command_code,
        }
        self._save_pending_approval(pending)

        if requires_command_code:
            msg = (
                f"High-risk action {action_type} requires your command code. "
                "Say: Runeforge command code YOURCODE. "
                "Or say Runeforge no to cancel."
            )
        else:
            msg = (
                f"Action {action_type} requires confirmation. "
                "Say Runeforge yes to proceed or Runeforge no to cancel."
            )
        self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="warning")
        self.bus.emit_event("runeforge", "os_action_approval_requested", {"ok": True, "pending": pending, "message": msg}, level="warning")
        return {"ok": True, "message": "os action approval requested", "pending": pending}

    def _load_sentinel_recommendations(self) -> list[dict[str, Any]]:
        state_path = self.bus.state / "security_sentinel.json"
        if not state_path.exists():
            return []

        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        stability = payload.get("stability") if isinstance(payload, dict) and isinstance(payload.get("stability"), dict) else {}
        process_recs = stability.get("process_recommendations") if isinstance(stability, dict) and isinstance(stability.get("process_recommendations"), dict) else {}
        recs = process_recs.get("recommendations") if isinstance(process_recs.get("recommendations"), list) else []

        output: list[dict[str, Any]] = []
        for item in recs:
            if not isinstance(item, dict):
                continue
            pid = int(item.get("pid", 0) or 0)
            if pid <= 0:
                continue
            output.append(
                {
                    "pid": pid,
                    "name": str(item.get("name", "process")),
                    "rss_mb": int(item.get("rss_mb", 0) or 0),
                    "recommendation": str(item.get("recommendation", "")),
                }
            )
        return output

    def request_sentinel_plan_approval(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        params = args or {}
        recommendations = self._load_sentinel_recommendations()
        if not recommendations:
            return {"ok": False, "message": "no sentinel recommendations available"}

        requested = params.get("pids") if isinstance(params.get("pids"), list) else []
        requested_pids = {int(value) for value in requested if str(value).strip().isdigit()}
        accept_all = bool(params.get("accept_all", not requested_pids))
        targets = recommendations if accept_all else [item for item in recommendations if int(item.get("pid", 0) or 0) in requested_pids]
        if not targets:
            return {
                "ok": False,
                "message": "no matching recommended processes for approval request",
                "available": recommendations,
            }

        estimated_restore_mb = sum(int(item.get("rss_mb", 0) or 0) for item in targets)
        approval = {
            "type": "sentinel_plan",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "accept_all": accept_all,
            "requested_pids": sorted(list(requested_pids)),
            "targets": targets,
            "estimated_restore_mb": estimated_restore_mb,
            "pre_available_memory_mb": self._system_memory_available_mb(),
        }
        self._save_pending_approval(approval)

        top_names = ", ".join(str(item.get("name", "process")).replace(".exe", "") for item in targets[:3])
        voice_message = (
            "Sentinel submitted a stabilization plan requiring your approval. "
            f"Suggested closures: {top_names}. "
            f"Estimated memory recovery is about {estimated_restore_mb} megabytes. "
            "Reply with: Runeforge yes to execute, or Runeforge no to cancel."
        )
        self.bus.emit_event("runeforge", "voice_feedback", {"message": voice_message}, level="warning")
        self.bus.emit_event(
            "runeforge",
            "sentinel_plan_approval_requested",
            {
                "ok": True,
                "approval": approval,
                "message": voice_message,
            },
            level="warning",
        )
        return {
            "ok": True,
            "message": "sentinel plan approval requested",
            "approval": approval,
        }

    def _terminate_pid(self, pid: int) -> dict[str, Any]:
        if pid <= 0:
            return {"ok": False, "pid": pid, "message": "invalid pid"}
        if pid == os.getpid():
            return {"ok": False, "pid": pid, "message": "refusing to terminate own process"}

        try:
            import psutil  # type: ignore

            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
                proc.wait(timeout=3)
            return {"ok": True, "pid": pid, "name": proc_name, "method": "psutil"}
        except Exception:
            pass

        if os.name == "nt":
            try:
                subprocess.check_output(["taskkill", "/PID", str(pid), "/F"], text=True, stderr=subprocess.STDOUT, timeout=8)
                return {"ok": True, "pid": pid, "method": "taskkill"}
            except Exception as ex:
                return {"ok": False, "pid": pid, "message": str(ex)}

        try:
            os.kill(pid, signal.SIGTERM)
            return {"ok": True, "pid": pid, "method": "os.kill"}
        except Exception as ex:
            return {"ok": False, "pid": pid, "message": str(ex)}

    def accept_sentinel_recommendations(self, args: dict[str, Any]) -> dict[str, Any]:
        pre_available_mb = self._system_memory_available_mb()
        recommendations = self._load_sentinel_recommendations()
        if not recommendations:
            return {"ok": False, "message": "no sentinel recommendations available"}

        pid_list = args.get("pids") if isinstance(args.get("pids"), list) else []
        selected_pids = {int(value) for value in pid_list if str(value).strip().isdigit()}
        accept_all = bool(args.get("accept_all", not selected_pids))

        if accept_all:
            targets = recommendations
        else:
            targets = [item for item in recommendations if int(item.get("pid", 0) or 0) in selected_pids]

        if not targets:
            return {
                "ok": False,
                "message": "no matching recommended processes to terminate",
                "available": recommendations,
            }

        results: list[dict[str, Any]] = []
        for item in targets:
            pid = int(item.get("pid", 0) or 0)
            outcome = self._terminate_pid(pid)
            outcome["recommended_name"] = str(item.get("name", "process"))
            outcome["recommended_rss_mb"] = int(item.get("rss_mb", 0) or 0)
            results.append(outcome)

        terminated = [item for item in results if item.get("ok")]
        failed = [item for item in results if not item.get("ok")]
        estimated_restored_mb = sum(int(item.get("recommended_rss_mb", 0) or 0) for item in terminated)
        post_available_mb = self._system_memory_available_mb()
        observed_restore_mb = None
        if pre_available_mb is not None and post_available_mb is not None:
            observed_restore_mb = post_available_mb - pre_available_mb

        if terminated:
            names = ", ".join(str(item.get("recommended_name", "process")).replace(".exe", "") for item in terminated[:3])
            voice_message = (
                "Runeforge applied Sentinel recommendations with user approval. "
                f"Terminated {len(terminated)} process or processes: {names}. "
                f"Estimated memory restored: {estimated_restored_mb} megabytes."
            )
            if observed_restore_mb is not None:
                voice_message += f" Observed available memory delta: {observed_restore_mb} megabytes."
            if failed:
                voice_message += f" {len(failed)} could not be terminated."
            self.bus.emit_event("runeforge", "voice_feedback", {"message": voice_message}, level="warning")
        else:
            self.bus.emit_event("runeforge", "voice_feedback", {"message": "Runeforge could not terminate the recommended processes."}, level="warning")

        self.bus.emit_event(
            "runeforge",
            "sentinel_recommendations_applied",
            {
                "accept_all": accept_all,
                "requested_pids": sorted(list(selected_pids)),
                "terminated_count": len(terminated),
                "failed_count": len(failed),
                "estimated_restored_mb": estimated_restored_mb,
                "observed_available_memory_delta_mb": observed_restore_mb,
                "results": results,
            },
            level="warning" if failed else "info",
        )

        return {
            "ok": bool(terminated),
            "accept_all": accept_all,
            "requested_pids": sorted(list(selected_pids)),
            "terminated": terminated,
            "failed": failed,
            "report": {
                "execution_method": "terminate recommended process ids",
                "terminated_count": len(terminated),
                "failed_count": len(failed),
                "estimated_restored_mb": estimated_restored_mb,
                "observed_available_memory_delta_mb": observed_restore_mb,
                "pre_available_memory_mb": pre_available_mb,
                "post_available_memory_mb": post_available_mb,
            },
        }

    def respond_sentinel_plan_approval(self, args: dict[str, Any]) -> dict[str, Any]:
        pending = self._load_pending_approval()
        if str(pending.get("type", "")).strip().lower() != "sentinel_plan":
            return {"ok": False, "message": "no pending sentinel plan awaiting approval"}

        approved = bool(args.get("approved", False))
        source = str(args.get("source", "text")).strip() or "text"
        if not approved:
            self._clear_pending_approval()
            msg = "Sentinel plan rejected. No process actions were executed."
            self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="info")
            self.bus.emit_event("runeforge", "sentinel_plan_approval_result", {"ok": True, "approved": False, "source": source, "message": msg}, level="info")
            return {"ok": True, "approved": False, "message": msg}

        targets = pending.get("targets") if isinstance(pending.get("targets"), list) else []
        pids = [int(item.get("pid", 0) or 0) for item in targets if isinstance(item, dict)]
        accept_all = bool(pending.get("accept_all", not pids))
        execution = self.accept_sentinel_recommendations({"accept_all": accept_all, "pids": pids})
        self._clear_pending_approval()

        report = execution.get("report") if isinstance(execution.get("report"), dict) else {}
        self.bus.emit_event(
            "runeforge",
            "sentinel_plan_approval_result",
            {
                "ok": bool(execution.get("ok")),
                "approved": True,
                "source": source,
                "execution": execution,
                "report": report,
            },
            level="warning" if not execution.get("ok") else "info",
        )
        return {
            "ok": bool(execution.get("ok")),
            "approved": True,
            "source": source,
            "execution": execution,
            "report": report,
        }

    def respond_pending_approval(self, args: dict[str, Any]) -> dict[str, Any]:
        pending = self._load_pending_approval()
        ptype = str(pending.get("type", "")).strip().lower()
        if ptype == "sentinel_plan":
            return self.respond_sentinel_plan_approval(args)
        if ptype != "os_action":
            return {"ok": False, "message": "no pending approval"}

        approved = bool(args.get("approved", False))
        source = str(args.get("source", "text")).strip() or "text"
        action = pending.get("action") if isinstance(pending.get("action"), dict) else None
        if not action:
            self._clear_pending_approval()
            return {"ok": False, "message": "pending approval action missing"}

        if not approved:
            self._clear_pending_approval()
            msg = "High-risk action rejected. No command executed."
            self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="info")
            self.bus.emit_event("runeforge", "os_action_approval_result", {"ok": True, "approved": False, "source": source, "message": msg}, level="info")
            return {"ok": True, "approved": False, "message": msg}

        command_code = str(args.get("command_code", "")).strip() if args.get("command_code") is not None else ""
        requires_command_code = bool(pending.get("requires_command_code", True))
        if requires_command_code and not command_code:
            msg = "Command code required before executing this high-risk action. Say: Runeforge command code YOURCODE."
            self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="warning")
            return {
                "ok": False,
                "approved": False,
                "requires_command_code": True,
                "message": msg,
            }
        cli_args = ["--action-json", json.dumps(action), "--agent", "runeforge"]
        if command_code:
            cli_args.extend(["--command-code", command_code])
        os_result = self._run_os_command_processor(cli_args, timeout_seconds=180)
        self._clear_pending_approval()

        report = {
            "execution_method": "command_processor",
            "action_type": str(action.get("action_type", "")),
            "ok": bool(os_result.get("ok")),
            "returncode": os_result.get("returncode"),
        }
        msg = "Approved high-risk action executed." if os_result.get("ok") else "Approved high-risk action failed during execution."
        self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="info" if os_result.get("ok") else "warning")
        self.bus.emit_event(
            "runeforge",
            "os_action_approval_result",
            {
                "ok": bool(os_result.get("ok")),
                "approved": True,
                "source": source,
                "action": action,
                "result": os_result.get("parsed") if isinstance(os_result.get("parsed"), dict) else os_result,
                "report": report,
            },
            level="info" if os_result.get("ok") else "warning",
        )
        return {
            "ok": bool(os_result.get("ok")),
            "approved": True,
            "source": source,
            "result": os_result.get("parsed") if isinstance(os_result.get("parsed"), dict) else os_result,
            "report": report,
        }

    def _run_voice_dictation(self, args: list[str], timeout_seconds: int = 120) -> dict[str, Any]:
        voice_script = self._voice_dictation_path()
        if not voice_script.exists():
            return {"ok": False, "message": f"voice dictation script not found: {voice_script}"}

        try:
            proc = subprocess.run(
                [sys.executable, str(voice_script), *args],
                cwd=str(self.os_edition_dir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except Exception as ex:
            return {"ok": False, "message": str(ex)}

        payload: dict[str, Any] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
        for line in reversed(payload["stdout"].splitlines()):
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    payload["parsed"] = parsed
                    break
            except json.JSONDecodeError:
                continue
        return payload

    def run_voice_text(self, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text", "")).strip()
        if not text:
            return {"ok": False, "message": "args.text is required"}

        command_code = str(args.get("command_code", "")).strip() if args.get("command_code") is not None else ""
        result = self._execute_voice_text(text, command_code)
        return {"ok": bool(result.get("ok")), "voice_result": result}

    def listen_voice_once(self, args: dict[str, Any]) -> dict[str, Any]:
        command_code = str(args.get("command_code", "")).strip() if args.get("command_code") is not None else ""
        captured = self._capture_spoken_text_once()
        if not captured.get("ok"):
            return {"ok": False, "voice_result": captured}
        spoken = str(captured.get("spoken_text", "")).strip()
        result = self._execute_voice_text(spoken, command_code)
        return {"ok": bool(result.get("ok")), "voice_result": result}

    def run_os_observation(self) -> dict[str, Any]:
        result = self._run_os_command_processor(["--observe"], timeout_seconds=180)
        parsed = result.get("parsed", {}) if isinstance(result.get("parsed"), dict) else {}
        observation = parsed.get("observation") if isinstance(parsed, dict) else None
        return {
            "ok": bool(result.get("ok")),
            "observation": observation,
            "command_processor": {
                "returncode": result.get("returncode"),
                "stderr": result.get("stderr", ""),
            },
        }

    def run_os_action(self, args: dict[str, Any]) -> dict[str, Any]:
        action = args.get("action")
        command_code = str(args.get("command_code", "")).strip() if args.get("command_code") is not None else ""
        if not isinstance(action, dict):
            return {"ok": False, "message": "args.action must be an object"}

        action_type = str(action.get("action_type", "")).strip()
        confirmed = bool(args.get("approved", False) or args.get("confirmed", False))
        if not confirmed:
            if action_type in self._command_code_required_action_types():
                return self.request_os_action_approval({"action": action, "source": "command", "requires_command_code": True})
            if action_type in self._confirmation_only_action_types():
                return self.request_os_action_approval({"action": action, "source": "command", "requires_command_code": False})

        cli_args = ["--action-json", json.dumps(action), "--agent", "runeforge"]
        if command_code:
            cli_args.extend(["--command-code", command_code])

        result = self._run_os_command_processor(cli_args, timeout_seconds=180)
        parsed = result.get("parsed", {}) if isinstance(result.get("parsed"), dict) else {}
        return {
            "ok": bool(result.get("ok")),
            "action_result": parsed if parsed else None,
            "command_processor": {
                "returncode": result.get("returncode"),
                "stderr": result.get("stderr", ""),
                "stdout": result.get("stdout", ""),
            },
        }

    def list_os_actions(self) -> dict[str, Any]:
        schema_path = self.os_edition_dir / "action_schema.json"
        if not schema_path.exists():
            return {"ok": False, "message": f"action schema not found: {schema_path}"}
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            return {"ok": False, "message": str(ex)}

        return {
            "ok": True,
            "supported_action_types": payload.get("supported_action_types", []),
            "high_risk_action_types": payload.get("high_risk_action_types", []),
            "schema_version": payload.get("version", "unknown"),
        }

    def _ensure_profile(self) -> None:
        if not self.profile_path.exists():
            self.profile_path.write_text(json.dumps(RUNEFORGE_PROFILE, indent=2), encoding="utf-8")
            return

        profile = self._load_profile()
        changed = False
        for key, value in RUNEFORGE_PROFILE.items():
            if key not in profile:
                profile[key] = value
                changed = True
        if not isinstance(profile.get("llm_router"), dict):
            profile["llm_router"] = RUNEFORGE_PROFILE["llm_router"]
            changed = True
        if changed:
            self._save_profile(profile)

    def _load_tasks(self) -> None:
        if not self.tasks_path.exists():
            return
        try:
            payload = json.loads(self.tasks_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if isinstance(items, list):
            self.tasks = [item for item in items if isinstance(item, dict)]

    def _save_tasks(self) -> None:
        self.tasks_path.write_text(json.dumps({"items": self.tasks}, indent=2), encoding="utf-8")

    def add_work_packet(self, args: dict[str, Any]) -> dict[str, Any]:
        packet = {
            "id": str(args.get("id", "")).strip() or f"packet_{len(self.tasks) + 1}",
            "objective": str(args.get("objective", "")).strip(),
            "deliverables": args.get("deliverables") if isinstance(args.get("deliverables"), list) else [],
            "status": "queued",
        }
        self.tasks.append(packet)
        self._save_tasks()
        return {"ok": True, "task": packet, "queued_total": len(self.tasks)}

    def add_work_item(self, args: dict[str, Any]) -> dict[str, Any]:
        item = {
            "packet_id": str(args.get("packet_id", "")).strip(),
            "title": str(args.get("title", "")).strip(),
            "details": str(args.get("details", "")).strip(),
            "owner": "runeforge",
            "status": "queued",
        }
        self.tasks.append(item)
        self._save_tasks()
        return {"ok": True, "work_item": item, "queued_total": len(self.tasks)}

    def list_tasks(self) -> dict[str, Any]:
        return {"ok": True, "tasks": self.tasks}

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") != "runeforge":
            return

        command = str(payload.get("command", ""))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}

        if command == "reality_weaving":
            result = self.reality_weaving(**args)
        elif command == "sigil_synthesis":
            result = self.sigil_synthesis(**args)
        elif command == "system_scribe":
            result = self.system_scribe(**args)
        elif command == "fate_threading":
            result = self.fate_threading(**args)
        elif command == "sanctum_of_invocation":
            result = self.sanctum_of_invocation(**args)
        elif command == "status_ping":
            result = {"ok": True, "status": "alive", "queued_tasks": len(self.tasks)}
        elif command == "work_packet":
            result = self.add_work_packet(args)
        elif command == "work_item":
            result = self.add_work_item(args)
        elif command == "list_tasks":
            result = self.list_tasks()
        elif command == "run_os_observation":
            result = self.run_os_observation()
        elif command == "run_os_action":
            result = self.run_os_action(args)
        elif command == "list_os_actions":
            result = self.list_os_actions()
        elif command == "voice_command":
            result = self.run_voice_text(args)
        elif command == "voice_listen":
            result = self.listen_voice_once(args)
        elif command == "request_sentinel_plan_approval":
            result = self.request_sentinel_plan_approval(args)
        elif command == "respond_sentinel_plan_approval":
            result = self.respond_sentinel_plan_approval(args)
        elif command == "respond_pending_approval":
            result = self.respond_pending_approval(args)
        elif command == "request_os_action_approval":
            result = self.request_os_action_approval(args)
        elif command == "accept_sentinel_recommendations":
            result = self.accept_sentinel_recommendations(args)
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("runeforge", f"command:{command}", result)
        self.bus.write_state(
            "runeforge",
            {
                "service": "runeforge",
                "pid": os.getpid(),
                "last_command": command,
                "queued_tasks": len(self.tasks),
                **result,
            },
        )

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "runeforge",
                {
                    "service": "runeforge",
                    "pid": os.getpid(),
                    "status": "idle",
                    "queued_tasks": len(self.tasks),
                },
            )
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Runeforge agent")
    parser.add_argument("--interval", type=int, default=9)
    args = parser.parse_args()

    agent = RuneforgeAgent(interval_seconds=args.interval)
    agent.run_forever()


if __name__ == "__main__":
    main()
