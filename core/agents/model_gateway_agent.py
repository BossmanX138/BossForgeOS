import argparse
import json
import os
import sys
import pathlib

# === Path Resolver for Bundled/Source Modes ===
def get_project_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        return pathlib.Path(sys.executable).parent
    return pathlib.Path(__file__).resolve().parent.parent.parent

PROJECT_ROOT = get_project_root()
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict
from urllib import error, request

from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.connectors.bossgate_connector import broadcast_presence, discover_transfer_targets, scan_rest_endpoints
from core.state.agent_memory_store import AgentMemoryStore


DEFAULT_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "provider": "ollama",
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "llama3.2",
        "api_key_env": "",
    },
    "vllm": {
        "provider": "openai_compatible",
        "url": "http://127.0.0.1:8000/v1/chat/completions",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "api_key_env": "",
    },
    "lmstudio": {
        "provider": "openai_compatible",
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model": "local-model",
        "api_key_env": "",
    },
}


class ModelGateway:
    def __init__(self, interval_seconds: int = 5, enable_presence_broadcast: bool = True) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.node_id_path = self.bus.state / "bossgate_node_id.txt"
        self.config_path = self.bus.state / "model_endpoints.json"
        self.profiles_path = self.bus.state / "model_profiles.json"
        self.mcp_path = self.bus.state / "mcp_servers.json"
        self.assistance_path = self.bus.state / "gateway_assistance_requests.json"
        self.locations_path = self.bus.state / "owned_gateway_locations.json"
        self.memory_db_path = self.bus.state / "gateway_memory.sqlite3"
        self.node_id = self._load_or_create_node_id()
        self.endpoints = self._load_endpoints()
        self.profiles = self._load_profiles()
        # Compatibility alias: newer control surfaces and commands refer to agent_profiles.
        self.agent_profiles = self.profiles
        self.mcp_servers = self._load_mcp_servers()
        self.memory_store = AgentMemoryStore(self.memory_db_path)
        self.servers: Dict[str, subprocess.Popen[Any]] = {}
        self.assistance_requests: Dict[str, Dict[str, Any]] = self._load_assistance_requests()
        self.owned_locations: Dict[str, Dict[str, Any]] = self._load_owned_locations()
        self.owned_agent_locations: Dict[str, Dict[str, Any]] = self._load_owned_locations()
        self._last_location_refresh = 0.0
        self._presence_stop_event = threading.Event()
        self._presence_thread: threading.Thread | None = None
        self.last_result: Dict[str, Any] = {"ok": True, "message": "idle"}
        if enable_presence_broadcast:
            self._start_presence_broadcast()

    def _load_endpoints(self) -> Dict[str, Dict[str, Any]]:
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw:
                    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
            except (OSError, json.JSONDecodeError):
                pass

        self.config_path.write_text(json.dumps(DEFAULT_ENDPOINTS, indent=2), encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_ENDPOINTS))

    def _save_endpoints(self) -> None:
        self.config_path.write_text(json.dumps(self.endpoints, indent=2), encoding="utf-8")

    def _load_or_create_node_id(self) -> str:
        if self.node_id_path.exists():
            try:
                existing = self.node_id_path.read_text(encoding="utf-8").strip()
                if existing:
                    return existing
            except OSError:
                pass
        generated = f"bossforgeos-{os.getpid()}-{int(time.time())}"
        self.node_id_path.write_text(generated, encoding="utf-8")
        return generated

    def _normalize_profile(self, key: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(profile)
        normalized["name"] = key

        encrypt_profile_raw = normalized.get("encrypt_profile")
        encrypt_profile = True if encrypt_profile_raw is None else bool(encrypt_profile_raw)
        normalized["encrypt_profile"] = encrypt_profile

        tools = normalized.get("tools")
        normalized["tools"] = sorted({str(t).strip() for t in tools if str(t).strip()}) if isinstance(tools, list) else []
        skills = normalized.get("skills")
        normalized["skills"] = sorted({str(s).strip().lower() for s in skills if str(s).strip()}) if isinstance(skills, list) else []
        sigils = normalized.get("sigils")
        normalized["sigils"] = sorted({str(s).strip().lower() for s in sigils if str(s).strip()}) if isinstance(sigils, list) else []

        profile_class = str(normalized.get("agent_class", "prime")).strip().lower()
        if profile_class == "core":
            profile_class = "normalized"
        normalized["agent_class"] = profile_class if profile_class in {"prime", "skilled", "normalized"} else "prime"

        bossgate_enabled_raw = normalized.get("bossgate_enabled")
        bossgate_enabled = True if bossgate_enabled_raw is None else bool(bossgate_enabled_raw)
        if not encrypt_profile:
            bossgate_enabled = False
        normalized["bossgate_enabled"] = bossgate_enabled

        has_llm_raw = normalized.get("has_llm")
        if isinstance(has_llm_raw, bool):
            has_llm = has_llm_raw
        else:
            has_llm = normalized["agent_class"] == "prime"

        # Policy: travel-capable (BossGate-enabled) agents must carry LLM inference capability.
        if bossgate_enabled:
            has_llm = True
        normalized["has_llm"] = has_llm

        normalized["memory_enabled"] = bool(normalized.get("memory_enabled", True))
        created_by_node = str(normalized.get("created_by_node", "")).strip()
        normalized["created_by_node"] = created_by_node or self.node_id
        current_node = str(normalized.get("current_node", "")).strip()
        normalized["current_node"] = current_node or self.node_id
        return normalized

    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        if self.profiles_path.exists():
            try:
                raw = json.loads(self.profiles_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    out: Dict[str, Dict[str, Any]] = {}
                    for k, v in raw.items():
                        if not isinstance(v, dict):
                            continue
                        key = str(k).strip().lower()
                        if not key:
                            continue
                        out[key] = self._normalize_profile(key, dict(v))
                    return out
            except (OSError, json.JSONDecodeError):
                pass
        self.profiles_path.write_text("{}", encoding="utf-8")
        return {}

    def _save_profiles(self) -> None:
        self.profiles_path.write_text(json.dumps(self.profiles, indent=2), encoding="utf-8")

    # Compatibility aliases for older/newer call-sites.
    def _normalize_agent_profile(self, key: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        return self._normalize_profile(key, profile)

    def _save_agent_profiles(self) -> None:
        self._save_profiles()

    def _load_mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        if self.mcp_path.exists():
            try:
                raw = json.loads(self.mcp_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
            except (OSError, json.JSONDecodeError):
                pass
        self.mcp_path.write_text("{}", encoding="utf-8")
        return {}

    def _save_mcp_servers(self) -> None:
        self.mcp_path.write_text(json.dumps(self.mcp_servers, indent=2), encoding="utf-8")

    def _load_assistance_requests(self) -> Dict[str, Dict[str, Any]]:
        if self.assistance_path.exists():
            try:
                raw = json.loads(self.assistance_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    out: Dict[str, Dict[str, Any]] = {}
                    for k, v in raw.items():
                        if isinstance(v, dict):
                            out[str(k).strip().lower()] = {
                                "requested": bool(v.get("requested", False)),
                                "reason": str(v.get("reason", "")).strip(),
                                "updated_at": int(v.get("updated_at", 0)) if isinstance(v.get("updated_at"), int) else 0,
                            }
                    return out
            except (OSError, json.JSONDecodeError):
                pass
        self.assistance_path.write_text("{}", encoding="utf-8")
        return {}

    def _save_assistance_requests(self) -> None:
        self.assistance_path.write_text(json.dumps(self.assistance_requests, indent=2), encoding="utf-8")

    def _load_owned_locations(self) -> Dict[str, Dict[str, Any]]:
        if self.locations_path.exists():
            try:
                raw = json.loads(self.locations_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return {str(k).strip().lower(): dict(v) for k, v in raw.items() if isinstance(v, dict)}
            except (OSError, json.JSONDecodeError):
                pass
        self.locations_path.write_text("{}", encoding="utf-8")
        return {}

    def _save_owned_locations(self) -> None:
        self.locations_path.write_text(json.dumps(self.owned_locations, indent=2), encoding="utf-8")

    def _save_owned_agent_locations(self) -> None:
        self.locations_path.write_text(json.dumps(self.owned_agent_locations, indent=2), encoding="utf-8")

    def _detect_format(self, file_path: str, format_hint: str = "") -> str:
        if format_hint.strip().lower() in {"json", "yaml"}:
            return format_hint.strip().lower()
        suffix = Path(file_path).suffix.lower()
        if suffix in {".yaml", ".yml"}:
            return "yaml"
        return "json"

    def _snapshot_config(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "endpoints": self.endpoints,
            "profiles": self.profiles,
            "mcp_servers": self.mcp_servers,
        }

    def _load_payload_text(self, file_path: str, format_name: str) -> Dict[str, Any]:
        raw = Path(file_path).read_text(encoding="utf-8")
        if format_name == "yaml":
            try:
                import yaml  # type: ignore
            except Exception:
                raise RuntimeError("PyYAML is required for YAML import/export. Install with: pip install pyyaml")
            data = yaml.safe_load(raw)  # type: ignore[attr-defined]
        else:
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise RuntimeError("config root must be an object")
        return data

    def _dump_payload_text(self, payload: Dict[str, Any], format_name: str) -> str:
        if format_name == "yaml":
            try:
                import yaml  # type: ignore
            except Exception:
                raise RuntimeError("PyYAML is required for YAML import/export. Install with: pip install pyyaml")
            return str(yaml.safe_dump(payload, sort_keys=False))  # type: ignore[attr-defined]
        return json.dumps(payload, indent=2)

    def export_config(self, file_path: str, format_hint: str = "") -> Dict[str, Any]:
        format_name = self._detect_format(file_path, format_hint)
        payload = self._snapshot_config()
        text = self._dump_payload_text(payload, format_name)
        target = Path(file_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return {"ok": True, "file": str(target), "format": format_name}

    def import_config(self, file_path: str, format_hint: str = "", merge: bool = False) -> Dict[str, Any]:
        format_name = self._detect_format(file_path, format_hint)
        source = Path(file_path).expanduser().resolve()
        if not source.exists():
            return {"ok": False, "message": f"config file not found: {source}"}

        try:
            payload = self._load_payload_text(str(source), format_name)
        except Exception as ex:
            return {"ok": False, "message": str(ex)}

        imported_endpoints = payload.get("endpoints", {})
        imported_profiles = payload.get("profiles", {})
        imported_mcp = payload.get("mcp_servers", {})

        if not isinstance(imported_endpoints, dict) or not isinstance(imported_profiles, dict) or not isinstance(imported_mcp, dict):
            return {"ok": False, "message": "endpoints, profiles, and mcp_servers must be objects"}

        if merge:
            self.endpoints.update({str(k): dict(v) for k, v in imported_endpoints.items() if isinstance(v, dict)})
            self.profiles.update({str(k): dict(v) for k, v in imported_profiles.items() if isinstance(v, dict)})
            self.mcp_servers.update({str(k): dict(v) for k, v in imported_mcp.items() if isinstance(v, dict)})
        else:
            self.endpoints = {str(k): dict(v) for k, v in imported_endpoints.items() if isinstance(v, dict)}
            self.profiles = {str(k): dict(v) for k, v in imported_profiles.items() if isinstance(v, dict)}
            self.mcp_servers = {str(k): dict(v) for k, v in imported_mcp.items() if isinstance(v, dict)}

        for key, profile in list(self.profiles.items()):
            if not isinstance(profile, dict):
                self.profiles.pop(key, None)
                continue
            self.profiles[key] = self._normalize_profile(key, profile)

        self._save_endpoints()
        self._save_profiles()
        self._save_mcp_servers()

        return {
            "ok": True,
            "file": str(source),
            "format": format_name,
            "merge": merge,
            "counts": {
                "endpoints": len(self.endpoints),
                "profiles": len(self.profiles),
                "mcp_servers": len(self.mcp_servers),
            },
        }

    def _agent_state_name(self, name: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in name.strip().lower())
        return f"model_agent_{safe}"

    def _write_agent_presence(self, name: str, endpoint: str, status: str, detail: str = "") -> None:
        self.bus.write_state(
            self._agent_state_name(name),
            {
                "service": "model_agent",
                "agent_name": name.strip().lower(),
                "endpoint": endpoint,
                "status": status,
                "detail": detail,
            },
        )

    def _emit_command_result(self, command: str, result: Dict[str, Any]) -> None:
        event_payload = dict(result)
        text = event_payload.get("text")
        if isinstance(text, str) and len(text) > 1200:
            event_payload["text"] = text[:1200] + "..."
        self.bus.emit_event("model_gateway", f"command:{command}", event_payload)
        self.last_result = result

    def _list_servers(self) -> list[Dict[str, Any]]:
        out: list[Dict[str, Any]] = []
        for name, proc in self.servers.items():
            out.append(
                {
                    "name": name,
                    "pid": proc.pid,
                    "running": proc.poll() is None,
                }
            )
        return out

    def _start_server(self, name: str, model: str, port: int, host: str) -> Dict[str, Any]:
        key = name.strip().lower()
        if key in self.servers and self.servers[key].poll() is None:
            proc = self.servers[key]
            return {"ok": True, "message": f"{key} already running", "pid": proc.pid}

        if key == "ollama":
            env = os.environ.copy()
            env.setdefault("OLLAMA_HOST", f"{host}:{port}")
            cmd = ["ollama", "serve"]
            try:
                proc = subprocess.Popen(cmd, env=env)
            except Exception as ex:
                return {"ok": False, "message": f"failed to start ollama: {ex}"}
            self.servers[key] = proc
            return {"ok": True, "server": key, "pid": proc.pid, "command": cmd}

        if key == "vllm":
            if not model:
                return {"ok": False, "message": "model is required for vllm"}
            cmd = [
                "python",
                "-m",
                "vllm.entrypoints.openai.api_server",
                "--model",
                model,
                "--host",
                host,
                "--port",
                str(port),
            ]
            try:
                proc = subprocess.Popen(cmd)
            except Exception as ex:
                return {"ok": False, "message": f"failed to start vllm: {ex}"}
            self.servers[key] = proc
            return {"ok": True, "server": key, "pid": proc.pid, "command": cmd}

        if key == "lmstudio":
            return {
                "ok": False,
                "message": "lmstudio local server must be started from LM Studio app (or its own CLI).",
            }

        return {"ok": False, "message": f"unsupported server: {name}"}

    def _stop_server(self, name: str) -> Dict[str, Any]:
        key = name.strip().lower()
        proc = self.servers.get(key)
        if proc is None:
            return {"ok": False, "message": f"server not tracked: {key}"}

        if proc.poll() is not None:
            return {"ok": True, "message": f"{key} already stopped", "pid": proc.pid}

        try:
            proc.terminate()
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        except Exception as ex:
            return {"ok": False, "message": f"failed stopping {key}: {ex}"}

        return {"ok": True, "message": f"stopped {key}", "pid": proc.pid}

    def _stop_all_servers(self) -> Dict[str, Any]:
        results: list[Dict[str, Any]] = []
        for key in list(self.servers.keys()):
            results.append(self._stop_server(key))
        return {"ok": True, "results": results}

    def _chat_payload(self, prompt: str, system: str) -> list[Dict[str, str]]:
        messages: list[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _invoke_endpoint(self, endpoint_name: str, prompt: str, system: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        endpoint = self.endpoints.get(endpoint_name)
        if endpoint is None:
            return {"ok": False, "message": f"unknown endpoint: {endpoint_name}"}

        provider = str(endpoint.get("provider", "openai_compatible"))
        url = str(endpoint.get("url", "")).strip()
        model = str(endpoint.get("model", "")).strip()
        api_key_env = str(endpoint.get("api_key_env", "")).strip()

        if not url:
            return {"ok": False, "message": f"endpoint '{endpoint_name}' has no url"}
        if not model:
            return {"ok": False, "message": f"endpoint '{endpoint_name}' has no model"}

        messages = self._chat_payload(prompt=prompt, system=system)
        payload: Dict[str, Any]
        if provider == "ollama":
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            }
        else:
            payload = {
                "model": model,
                "messages": messages,
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
            with request.urlopen(req, timeout=120) as resp:
                raw_bytes = resp.read()
        except error.HTTPError as ex:
            body = ""
            try:
                body = ex.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(ex)
            return {"ok": False, "message": f"HTTP {ex.code}: {body}"}
        except Exception as ex:
            return {"ok": False, "message": str(ex)}

        try:
            data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {"ok": False, "message": "endpoint returned invalid JSON"}

        if provider == "ollama":
            text = ((data.get("message") or {}).get("content") or "").strip()
        else:
            choices = data.get("choices") or []
            first = choices[0] if isinstance(choices, list) and choices else {}
            text = ((first.get("message") or {}).get("content") or "").strip()

        return {
            "ok": True,
            "endpoint": endpoint_name,
            "provider": provider,
            "model": model,
            "text": text,
            "usage": data.get("usage", {}),
        }

    def invoke_endpoint(self, endpoint_name: str, prompt: str, system: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        return self._invoke_endpoint(endpoint_name, prompt, system, temperature, max_tokens)

    def list_agent_profiles(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.agent_profiles)

    def create_agent_profile(
        self,
        name: str,
        endpoint: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        tools: list[str] | None = None,
        agent_class: str = "prime",
        has_llm: bool | None = None,
        bossgate_enabled: bool = True,
        encrypt_profile: bool = True,
        agent_type: str | None = None,
        rank: str | None = None,
        skills: list[str] | None = None,
        sigils: list[str] | None = None,
        dispatch_policy: Dict[str, Any] | None = None,
        personality_wrapper: Dict[str, Any] | None = None,
        system_wrapper: Dict[str, Any] | None = None,
        instructions: Dict[str, Any] | None = None,
        custom_icon_path: str | None = None,
    ) -> Dict[str, Any]:
        return self._create_agent_profile(
            name,
            endpoint,
            system_prompt,
            temperature,
            max_tokens,
            tools,
            agent_class,
            has_llm,
            bossgate_enabled,
            encrypt_profile,
            agent_type,
            rank,
            skills,
            sigils,
            dispatch_policy,
            personality_wrapper,
            system_wrapper,
            instructions,
            custom_icon_path,
        )

    def delete_agent_profile(self, name: str) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        if key not in self.agent_profiles:
            return {"ok": False, "message": f"agent not found: {key}"}
        del self.agent_profiles[key]
        self._save_agent_profiles()
        return {"ok": True, "message": f"agent deleted: {key}"}

    def run_agent_profile(
        self,
        name: str,
        task: str,
        override_endpoint: str = "",
        memory_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return self._run_agent_profile(name=name, task=task, override_endpoint=override_endpoint, memory_context=memory_context)

    def recall_agent_memory(self, name: str, limit: int = 25) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        interactions = self.memory_store.recall_interactions(agent_name=key, limit=limit)
        relationships = self.memory_store.list_relationships(agent_name=key)
        return {
            "ok": True,
            "agent": key,
            "interactions": interactions,
            "relationships": relationships,
            "memory_db": str(self.memory_db_path),
        }

    def list_mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.mcp_servers)

    def _presence_agents_snapshot(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for name, profile in self.agent_profiles.items():
            if not isinstance(profile, dict):
                continue
            assistance = self.assistance_requests.get(name, {})
            items.append(
                {
                    "name": name,
                    "agent_class": str(profile.get("agent_class", "prime")).strip().lower() or "prime",
                    "bossgate_enabled": bool(profile.get("bossgate_enabled", True)),
                    "created_by_node": str(profile.get("created_by_node", self.node_id)).strip() or self.node_id,
                    "current_node": self.node_id,
                    "assistance_requested": bool(assistance.get("requested", False)),
                    "assistance_reason": str(assistance.get("reason", "")).strip(),
                }
            )
        return items

    def _start_presence_broadcast(self) -> None:
        if os.environ.get("BOSSGATE_DISABLE_PRESENCE_BROADCAST", "").strip().lower() in {"1", "true", "yes", "on"}:
            return
        if self._presence_thread is not None and self._presence_thread.is_alive():
            return
        self._presence_thread = threading.Thread(
            target=broadcast_presence,
            kwargs={
                "node_id": self.node_id,
                "agents_provider": self._presence_agents_snapshot,
                "interval_seconds": 2.0,
                "stop_event": self._presence_stop_event,
            },
            daemon=True,
        )
        self._presence_thread.start()

    def set_agent_assistance_request(self, name: str, requested: bool, reason: str = "") -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        if key not in self.agent_profiles:
            return {"ok": False, "message": f"agent not found: {key}"}
        self.assistance_requests[key] = {
            "requested": bool(requested),
            "reason": reason.strip(),
            "updated_at": int(time.time()),
        }
        self._save_assistance_requests()
        return {
            "ok": True,
            "agent": key,
            "assistance_requested": bool(requested),
            "assistance_reason": reason.strip(),
        }

    def list_assistance_requests(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "requests": dict(self.assistance_requests),
        }

    def _refresh_owned_agent_locations(self, timeout: int = 1) -> Dict[str, Any]:
        now = int(time.time())
        owned_agent_names = {
            name
            for name, profile in self.agent_profiles.items()
            if isinstance(profile, dict) and str(profile.get("created_by_node", self.node_id)).strip() == self.node_id
        }

        refreshed: Dict[str, Dict[str, Any]] = {}
        for name in owned_agent_names:
            profile = self.agent_profiles.get(name) or {}
            assistance = self.assistance_requests.get(name, {})
            refreshed[name] = {
                "agent_name": name,
                "created_by_node": self.node_id,
                "current_node": self.node_id,
                "node_id": self.node_id,
                "address": "127.0.0.1",
                "last_seen": now,
                "online": True,
                "assistance_requested": bool(assistance.get("requested", False)),
                "assistance_reason": str(assistance.get("reason", "")).strip(),
                "source": "local",
                "target_type": "bossforgeos",
                "agent_class": str(profile.get("agent_class", "prime")).strip().lower() or "prime",
            }

        discovered = discover_transfer_targets(timeout=max(1, int(timeout)), assistance_only=False)
        for item in discovered:
            if not isinstance(item, dict):
                continue
            agent_name = str(item.get("agent_name", "")).strip().lower()
            if not agent_name:
                continue
            created_by_node = str(item.get("created_by_node", "")).strip()
            if created_by_node != self.node_id and agent_name not in owned_agent_names:
                continue
            refreshed[agent_name] = {
                "agent_name": agent_name,
                "created_by_node": created_by_node or self.node_id,
                "current_node": str(item.get("current_node", item.get("node_id", ""))).strip() or str(item.get("node_id", "")).strip(),
                "node_id": str(item.get("node_id", "")).strip(),
                "address": str(item.get("address", "")).strip(),
                "last_seen": now,
                "online": True,
                "assistance_requested": bool(item.get("assistance_requested", False)),
                "assistance_reason": str(item.get("assistance_reason", "")).strip(),
                "source": "beacon",
                "target_type": str(item.get("target_type", "bossgate_connector")).strip().lower() or "bossgate_connector",
                "agent_class": str(item.get("agent_class", "prime")).strip().lower() or "prime",
            }

        self.owned_agent_locations = refreshed
        self._save_owned_agent_locations()
        return {
            "ok": True,
            "owner_node": self.node_id,
            "agents": dict(self.owned_agent_locations),
        }

    def list_owned_agent_locations(self, refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            return self._refresh_owned_agent_locations(timeout=1)
        return {
            "ok": True,
            "owner_node": self.node_id,
            "agents": dict(self.owned_agent_locations),
        }

    def discover_travel_targets(self, timeout: int = 5, assistance_only: bool = False) -> Dict[str, Any]:
        safe_timeout = max(1, int(timeout))
        targets = discover_transfer_targets(timeout=safe_timeout, assistance_only=bool(assistance_only))
        return {
            "ok": True,
            "timeout": safe_timeout,
            "assistance_only": bool(assistance_only),
            "targets": targets,
            "policy": "travel_allowed_only_to_bossgate_ass_bossforgeos_bridgebase_alpha",
        }

    def validate_transfer_target(self, destination: str) -> Dict[str, Any]:
        target = destination.strip()
        if not target:
            return {"ok": False, "message": "destination is required", "allowed_for_transfer": False}
        result = scan_rest_endpoints(target)
        if not isinstance(result, dict):
            return {
                "ok": False,
                "message": "invalid transfer validation result",
                "allowed_for_transfer": False,
                "destination": target,
            }
        result.setdefault("destination", target)
        return result

    def set_mcp_server(self, name: str, command: str, args: list[str] | None = None, env: Dict[str, str] | None = None) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        if not command.strip():
            return {"ok": False, "message": "command is required"}
        payload = {
            "name": key,
            "command": command.strip(),
            "args": [str(a) for a in (args or [])],
            "env": {str(k): str(v) for k, v in (env or {}).items()},
        }
        self.mcp_servers[key] = payload
        self._save_mcp_servers()
        return {"ok": True, "server": payload}

    def remove_mcp_server(self, name: str) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        if key not in self.mcp_servers:
            return {"ok": False, "message": f"mcp server not found: {key}"}
        del self.mcp_servers[key]
        self._save_mcp_servers()
        return {"ok": True, "message": f"mcp server removed: {key}"}

    def _create_agent_profile(
        self,
        name: str,
        endpoint: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        tools: list[str] | None = None,
        agent_class: str = "prime",
        has_llm: bool | None = None,
        bossgate_enabled: bool = True,
        encrypt_profile: bool = True,
        agent_type: str | None = None,
        rank: str | None = None,
        skills: list[str] | None = None,
        sigils: list[str] | None = None,
        dispatch_policy: Dict[str, Any] | None = None,
        personality_wrapper: Dict[str, Any] | None = None,
        system_wrapper: Dict[str, Any] | None = None,
        instructions: Dict[str, Any] | None = None,
        custom_icon_path: str | None = None,
    ) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "agent name is required"}
        if endpoint not in self.endpoints:
            return {"ok": False, "message": f"unknown endpoint: {endpoint}"}

        klass = agent_class.strip().lower()
        if klass == "core":
            klass = "normalized"
        if klass not in {"prime", "skilled", "normalized"}:
            klass = "prime"
        llm_enabled = (klass == "prime") if has_llm is None else bool(has_llm)

        profile = {
            "name": key,
            "id": key,
            "endpoint": endpoint,
            "system": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": sorted({str(t).strip() for t in (tools or []) if str(t).strip()}),
            "agent_class": klass,
            "has_llm": llm_enabled,
            "bossgate_enabled": bool(bossgate_enabled),
            "encrypt_profile": bool(encrypt_profile),
            "created_by_node": self.node_id,
            "current_node": self.node_id,
            "memory_enabled": True,
        }
        if agent_type:
            profile["agent_type"] = str(agent_type).strip().lower()
        if rank:
            profile["rank"] = str(rank).strip().lower()
        if isinstance(skills, list):
            profile["skills"] = sorted({str(item).strip().lower() for item in skills if str(item).strip()})
        if isinstance(sigils, list):
            profile["sigils"] = sorted({str(item).strip().lower() for item in sigils if str(item).strip()})
        if isinstance(dispatch_policy, dict):
            profile["dispatch_policy"] = dict(dispatch_policy)
        if isinstance(personality_wrapper, dict):
            profile_metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
            profile_metadata["personality_wrapper"] = {
                "preset": str(personality_wrapper.get("preset", "balanced")).strip().lower() or "balanced",
                "notes": str(personality_wrapper.get("notes", "")).strip(),
                "behavior_patterns": [
                    str(item).strip().lower()
                    for item in (personality_wrapper.get("behavior_patterns") if isinstance(personality_wrapper.get("behavior_patterns"), list) else [])
                    if str(item).strip()
                ],
                "interests": [
                    str(item).strip().lower()
                    for item in (personality_wrapper.get("interests") if isinstance(personality_wrapper.get("interests"), list) else [])
                    if str(item).strip()
                ],
            }
            profile["metadata"] = profile_metadata
        if isinstance(system_wrapper, dict):
            profile["system_wrapper"] = {
                "enabled": bool(system_wrapper.get("enabled", True)),
                "name": str(system_wrapper.get("name", "personality_wrapper")).strip() or "personality_wrapper",
                "mode": str(system_wrapper.get("mode", "balanced")).strip().lower() or "balanced",
                "entrypoint": str(system_wrapper.get("entrypoint", "agentforge_personality_v1")).strip() or "agentforge_personality_v1",
                "contract_version": str(system_wrapper.get("contract_version", "1.0")).strip() or "1.0",
            }
        if isinstance(instructions, dict):
            profile["instructions"] = {
                "system": str(instructions.get("system", system_prompt)).strip() or str(system_prompt).strip(),
                "developer": str(instructions.get("developer", "")).strip(),
                "operational": instructions.get("operational") if isinstance(instructions.get("operational"), list) else [],
                "safety": instructions.get("safety") if isinstance(instructions.get("safety"), list) else [],
            }
        if custom_icon_path:
            profile["custom_icon_path"] = str(custom_icon_path).strip()
        profile = self._normalize_agent_profile(key, profile)
        self.agent_profiles[key] = profile
        self._save_agent_profiles()
        self.memory_store.register_agent(agent_name=key, agent_class=profile["agent_class"], has_llm=bool(profile.get("has_llm")))
        self._write_agent_presence(name=key, endpoint=endpoint, status="deployed", detail="profile saved")
        return {"ok": True, "agent": profile}

    def _run_agent_profile(
        self,
        name: str,
        task: str,
        override_endpoint: str = "",
        memory_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        key = name.strip().lower()
        profile = self.agent_profiles.get(key)
        if profile is None:
            return {"ok": False, "message": f"agent not found: {name}"}
        endpoint = override_endpoint.strip() or str(profile.get("endpoint", ""))
        if endpoint not in self.endpoints:
            return {"ok": False, "message": f"unknown endpoint: {endpoint}"}
        if not task.strip():
            return {"ok": False, "message": "task is required"}

        system = str(profile.get("system", "You are a helpful agent."))
        tools = profile.get("tools") or []
        if isinstance(tools, list) and tools:
            tool_specs: list[str] = []
            for tool_name in tools:
                if not isinstance(tool_name, str):
                    continue
                tool = self.mcp_servers.get(tool_name)
                if not isinstance(tool, dict):
                    continue
                tool_specs.append(f"- {tool_name}: command={tool.get('command', '')} args={tool.get('args', [])}")
            if tool_specs:
                system = f"{system}\n\nAvailable MCP tools for this agent:\n" + "\n".join(tool_specs)
        temperature = float(profile.get("temperature", 0.2))
        max_tokens = int(profile.get("max_tokens", 900))
        result = self._invoke_endpoint(endpoint, task, system, temperature, max_tokens)
        ctx = memory_context if isinstance(memory_context, dict) else {}
        self.memory_store.record_interaction(
            agent_name=key,
            task=task,
            success=bool(result.get("ok")),
            endpoint=endpoint,
            user_name=str(ctx.get("user", "")).strip(),
            employer_name=str(ctx.get("employer", "")).strip(),
            project_name=str(ctx.get("project", "")).strip(),
            counterpart_agent=str(ctx.get("counterpart_agent", "")).strip(),
            summary=str(result.get("text") or result.get("message") or "")[:400],
            details={
                "usage": result.get("usage", {}),
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
            },
        )
        if result.get("ok"):
            result["agent"] = key
            self._write_agent_presence(name=key, endpoint=endpoint, status="active", detail="task completed")
        return result

    def handle_command(self, payload: Dict[str, Any]) -> None:
        if payload.get("target") not in {"model_gateway", "ai_gateway", "llm_gateway"}:
            return

        command = str(payload.get("command", ""))
        args = payload.get("args") or {}

        if command == "status_ping":
            result = {
                "ok": True,
                "status": "alive",
                "endpoints": sorted(self.endpoints.keys()),
                "servers": self._list_servers(),
            }
        elif command == "list_endpoints":
            result = {"ok": True, "endpoints": self.endpoints}
        elif command == "list_agents":
            result = {"ok": True, "agents": self.agent_profiles}
        elif command == "create_agent":
            name = str(args.get("name", "")).strip()
            endpoint = str(args.get("endpoint", "")).strip()
            system_prompt = str(args.get("system", "You are a helpful specialist agent."))
            temperature = float(args.get("temperature", 0.2))
            max_tokens = int(args.get("max_tokens", 900))
            tools = args.get("tools")
            tools_list = tools if isinstance(tools, list) else []
            agent_class = str(args.get("agent_class", "prime")).strip()
            has_llm_raw = args.get("has_llm")
            has_llm = bool(has_llm_raw) if isinstance(has_llm_raw, bool) else None
            bossgate_enabled_raw = args.get("bossgate_enabled")
            bossgate_enabled = True if bossgate_enabled_raw is None else bool(bossgate_enabled_raw)
            encrypt_profile_raw = args.get("encrypt_profile")
            encrypt_profile = True if encrypt_profile_raw is None else bool(encrypt_profile_raw)
            agent_type = str(args.get("agent_type", "")).strip().lower() or None
            rank = str(args.get("rank", "")).strip().lower() or None
            skills_raw = args.get("skills")
            skills = skills_raw if isinstance(skills_raw, list) else None
            sigils_raw = args.get("sigils")
            sigils = sigils_raw if isinstance(sigils_raw, list) else None
            dispatch_policy_raw = args.get("dispatch_policy")
            dispatch_policy = dispatch_policy_raw if isinstance(dispatch_policy_raw, dict) else None
            custom_icon_path = str(args.get("custom_icon_path", "")).strip() or None
            result = self._create_agent_profile(
                name,
                endpoint,
                system_prompt,
                temperature,
                max_tokens,
                tools_list,
                agent_class,
                has_llm,
                bossgate_enabled,
                encrypt_profile,
                agent_type,
                rank,
                skills,
                sigils,
                dispatch_policy,
                custom_icon_path=custom_icon_path,
            )
        elif command == "list_mcp_servers":
            result = {"ok": True, "mcp_servers": self.mcp_servers}
        elif command == "set_mcp_server":
            name = str(args.get("name", "")).strip()
            command_str = str(args.get("command", "")).strip()
            raw_args = args.get("args")
            args_list = raw_args if isinstance(raw_args, list) else []
            raw_env = args.get("env")
            env_obj = raw_env if isinstance(raw_env, dict) else {}
            result = self.set_mcp_server(name=name, command=command_str, args=args_list, env=env_obj)
        elif command == "remove_mcp_server":
            name = str(args.get("name", "")).strip()
            result = self.remove_mcp_server(name)
        elif command == "export_config":
            file_path = str(args.get("file", "")).strip()
            format_hint = str(args.get("format", "")).strip()
            if not file_path:
                result = {"ok": False, "message": "file is required"}
            else:
                try:
                    result = self.export_config(file_path=file_path, format_hint=format_hint)
                except Exception as ex:
                    result = {"ok": False, "message": str(ex)}
        elif command == "import_config":
            file_path = str(args.get("file", "")).strip()
            format_hint = str(args.get("format", "")).strip()
            merge = bool(args.get("merge", False))
            if not file_path:
                result = {"ok": False, "message": "file is required"}
            else:
                result = self.import_config(file_path=file_path, format_hint=format_hint, merge=merge)
        elif command == "delete_agent":
            name = str(args.get("name", "")).strip()
            result = self.delete_agent_profile(name)
        elif command == "run_agent":
            name = str(args.get("name", "")).strip()
            task = str(args.get("task", "")).strip()
            endpoint = str(args.get("endpoint", "")).strip()
            memory_context = args.get("memory_context") if isinstance(args.get("memory_context"), dict) else {}
            result = self._run_agent_profile(name=name, task=task, override_endpoint=endpoint, memory_context=memory_context)
        elif command == "recall_agent_memory":
            name = str(args.get("name", "")).strip()
            limit = int(args.get("limit", 25))
            result = self.recall_agent_memory(name=name, limit=limit)
        elif command == "discover_travel_targets":
            timeout = int(args.get("timeout", 5))
            assistance_only = bool(args.get("assistance_only", False))
            result = self.discover_travel_targets(timeout=timeout, assistance_only=assistance_only)
        elif command == "validate_transfer_target":
            destination = str(args.get("destination", "")).strip()
            result = self.validate_transfer_target(destination)
        elif command == "set_agent_assistance_request":
            name = str(args.get("name", "")).strip()
            requested = bool(args.get("requested", True))
            reason = str(args.get("reason", "")).strip()
            result = self.set_agent_assistance_request(name=name, requested=requested, reason=reason)
        elif command == "list_agent_assistance_requests":
            result = self.list_assistance_requests()
        elif command == "list_owned_agent_locations":
            refresh = bool(args.get("refresh", False))
            result = self.list_owned_agent_locations(refresh=refresh)
        elif command == "list_servers":
            result = {"ok": True, "servers": self._list_servers()}
        elif command == "serve_model":
            server_name = str(args.get("server", "")).strip().lower()
            model = str(args.get("model", "")).strip()
            host = str(args.get("host", "127.0.0.1")).strip() or "127.0.0.1"
            port = int(args.get("port", 8000))
            if not server_name:
                result = {"ok": False, "message": "server is required"}
            else:
                result = self._start_server(name=server_name, model=model, port=port, host=host)
        elif command == "stop_model_server":
            server_name = str(args.get("server", "")).strip().lower()
            if not server_name:
                result = {"ok": False, "message": "server is required"}
            else:
                result = self._stop_server(server_name)
        elif command == "stop_all_model_servers":
            result = self._stop_all_servers()
        elif command == "set_endpoint":
            name = str(args.get("name", "")).strip().lower()
            if not name:
                result = {"ok": False, "message": "name is required"}
            else:
                current = dict(self.endpoints.get(name, {}))
                if "provider" in args:
                    current["provider"] = str(args.get("provider", "openai_compatible"))
                if "url" in args:
                    current["url"] = str(args.get("url", "")).strip()
                if "model" in args:
                    current["model"] = str(args.get("model", "")).strip()
                if "api_key_env" in args:
                    current["api_key_env"] = str(args.get("api_key_env", "")).strip()
                self.endpoints[name] = current
                self._save_endpoints()
                result = {"ok": True, "message": f"endpoint saved: {name}", "endpoint": current}
        elif command == "remove_endpoint":
            name = str(args.get("name", "")).strip().lower()
            if not name:
                result = {"ok": False, "message": "name is required"}
            elif name not in self.endpoints:
                result = {"ok": False, "message": f"endpoint not found: {name}"}
            else:
                del self.endpoints[name]
                self._save_endpoints()
                result = {"ok": True, "message": f"endpoint removed: {name}"}
        elif command == "invoke":
            endpoint = str(args.get("endpoint", "ollama"))
            prompt = str(args.get("prompt", "")).strip()
            system = str(args.get("system", "You are BossForgeOS Model Gateway."))
            temperature = float(args.get("temperature", 0.2))
            max_tokens = int(args.get("max_tokens", 900))
            if not prompt:
                result = {"ok": False, "message": "prompt is required"}
            else:
                result = self._invoke_endpoint(endpoint, prompt, system, temperature, max_tokens)
        elif command == "refactor_code":
            endpoint = str(args.get("endpoint", "ollama"))
            language = str(args.get("language", "code"))
            instructions = str(args.get("instructions", "Refactor for readability and maintainability."))
            code = str(args.get("code", ""))
            system = str(
                args.get(
                    "system",
                    "You are a senior software engineer. Return only the refactored code unless asked for explanation.",
                )
            )
            temperature = float(args.get("temperature", 0.1))
            max_tokens = int(args.get("max_tokens", 1800))
            if not code.strip():
                result = {"ok": False, "message": "code is required for refactor_code"}
            else:
                prompt = (
                    f"Refactor this {language} code. Follow instructions exactly.\n"
                    f"Instructions: {instructions}\n\n"
                    f"Code:\n{code}"
                )
                result = self._invoke_endpoint(endpoint, prompt, system, temperature, max_tokens)
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self._emit_command_result(command, result)

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            for _, cmd_payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(cmd_payload)

            if time.time() - self._last_location_refresh >= max(2.0, float(self.interval_seconds)):
                self._refresh_owned_agent_locations(timeout=1)
                self._last_location_refresh = time.time()

            self.bus.write_state(
                "model_gateway",
                {
                    "service": "model_gateway",
                    "pid": os.getpid(),
                    "node_id": self.node_id,
                    "configured_endpoints": sorted(self.endpoints.keys()),
                    "agent_profiles": sorted(self.agent_profiles.keys()),
                    "mcp_servers": sorted(self.mcp_servers.keys()),
                    "assistance_requests": self.assistance_requests,
                    "owned_agent_locations": self.owned_agent_locations,
                    "travel_policy": "travel_allowed_only_to_bossgate_ass_bossforgeos_bridgebase_alpha",
                    "servers": self._list_servers(),
                    "last_result": self.last_result,
                },
            )
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


class ModelGatewayAgent(ModelGateway):
    """Compatibility wrapper preserving historic class name for callers."""
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS model gateway service")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    service = ModelGateway(interval_seconds=args.interval)
    service.run_forever()


if __name__ == "__main__":
    main()
