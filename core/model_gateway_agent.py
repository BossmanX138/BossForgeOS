import argparse
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict
from urllib import error, request

from core.rune_bus import RuneBus, resolve_root_from_env


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


class ModelGatewayAgent:
    def __init__(self, interval_seconds: int = 5) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.config_path = self.bus.state / "model_endpoints.json"
        self.agents_path = self.bus.state / "model_agents.json"
        self.mcp_path = self.bus.state / "mcp_servers.json"
        self.endpoints = self._load_endpoints()
        self.agent_profiles = self._load_agent_profiles()
        self.mcp_servers = self._load_mcp_servers()
        self.servers: Dict[str, subprocess.Popen[Any]] = {}
        self.last_result: Dict[str, Any] = {"ok": True, "message": "idle"}

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

    def _load_agent_profiles(self) -> Dict[str, Dict[str, Any]]:
        if self.agents_path.exists():
            try:
                raw = json.loads(self.agents_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
            except (OSError, json.JSONDecodeError):
                pass
        self.agents_path.write_text("{}", encoding="utf-8")
        return {}

    def _save_agent_profiles(self) -> None:
        self.agents_path.write_text(json.dumps(self.agent_profiles, indent=2), encoding="utf-8")

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
            "agents": self.agent_profiles,
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
        imported_agents = payload.get("agents", {})
        imported_mcp = payload.get("mcp_servers", {})

        if not isinstance(imported_endpoints, dict) or not isinstance(imported_agents, dict) or not isinstance(imported_mcp, dict):
            return {"ok": False, "message": "endpoints, agents, and mcp_servers must be objects"}

        if merge:
            self.endpoints.update({str(k): dict(v) for k, v in imported_endpoints.items() if isinstance(v, dict)})
            self.agent_profiles.update({str(k): dict(v) for k, v in imported_agents.items() if isinstance(v, dict)})
            self.mcp_servers.update({str(k): dict(v) for k, v in imported_mcp.items() if isinstance(v, dict)})
        else:
            self.endpoints = {str(k): dict(v) for k, v in imported_endpoints.items() if isinstance(v, dict)}
            self.agent_profiles = {str(k): dict(v) for k, v in imported_agents.items() if isinstance(v, dict)}
            self.mcp_servers = {str(k): dict(v) for k, v in imported_mcp.items() if isinstance(v, dict)}

        for key, profile in list(self.agent_profiles.items()):
            if not isinstance(profile, dict):
                self.agent_profiles.pop(key, None)
                continue
            tools = profile.get("tools")
            if not isinstance(tools, list):
                profile["tools"] = []

        self._save_endpoints()
        self._save_agent_profiles()
        self._save_mcp_servers()

        return {
            "ok": True,
            "file": str(source),
            "format": format_name,
            "merge": merge,
            "counts": {
                "endpoints": len(self.endpoints),
                "agents": len(self.agent_profiles),
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
    ) -> Dict[str, Any]:
        return self._create_agent_profile(name, endpoint, system_prompt, temperature, max_tokens, tools)

    def delete_agent_profile(self, name: str) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        if key not in self.agent_profiles:
            return {"ok": False, "message": f"agent not found: {key}"}
        del self.agent_profiles[key]
        self._save_agent_profiles()
        return {"ok": True, "message": f"agent deleted: {key}"}

    def run_agent_profile(self, name: str, task: str, override_endpoint: str = "") -> Dict[str, Any]:
        return self._run_agent_profile(name=name, task=task, override_endpoint=override_endpoint)

    def list_mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.mcp_servers)

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
    ) -> Dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "agent name is required"}
        if endpoint not in self.endpoints:
            return {"ok": False, "message": f"unknown endpoint: {endpoint}"}

        profile = {
            "name": key,
            "endpoint": endpoint,
            "system": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": sorted({str(t).strip() for t in (tools or []) if str(t).strip()}),
        }
        self.agent_profiles[key] = profile
        self._save_agent_profiles()
        self._write_agent_presence(name=key, endpoint=endpoint, status="deployed", detail="profile saved")
        return {"ok": True, "agent": profile}

    def _run_agent_profile(self, name: str, task: str, override_endpoint: str = "") -> Dict[str, Any]:
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
            result = self._create_agent_profile(name, endpoint, system_prompt, temperature, max_tokens, tools_list)
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
            result = self._run_agent_profile(name=name, task=task, override_endpoint=endpoint)
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

            self.bus.write_state(
                "model_gateway",
                {
                    "service": "model_gateway",
                    "pid": os.getpid(),
                    "configured_endpoints": sorted(self.endpoints.keys()),
                    "agent_profiles": sorted(self.agent_profiles.keys()),
                    "mcp_servers": sorted(self.mcp_servers.keys()),
                    "servers": self._list_servers(),
                    "last_result": self.last_result,
                },
            )
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS model gateway service")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    service = ModelGatewayAgent(interval_seconds=args.interval)
    service.run_forever()


if __name__ == "__main__":
    main()
