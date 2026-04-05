import argparse
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.security.security_vault import ensure_vault_file, protect_text, unprotect_text


SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[\"'][^\"']{8,}[\"']"),
]


class SecuritySentinelAgent:
    def __init__(self, interval_seconds: int = 20, root: Path | None = None) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(root or resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.vault_path = self.bus.state / "security_secrets_vault.json"
        self.policy_path = self.bus.state / "security_policy.json"
        ensure_vault_file(self.vault_path)
        self._ensure_policy()

    def _ensure_policy(self) -> None:
        if self.policy_path.exists():
            return
        default = {
            "version": 1,
            "default": "deny",
            "allow": {
                "archivist": ["scan_workspace"],
                "codemage": ["scan_workspace"],
                "model_gateway": ["scan_workspace"],
                "security_sentinel": ["*"],
            },
        }
        self.policy_path.write_text(json.dumps(default, indent=2), encoding="utf-8")

    def _read_vault(self) -> dict[str, str]:
        try:
            payload = json.loads(self.vault_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            return {}
        return {str(k): str(v) for k, v in payload.items()}

    def _write_vault(self, payload: dict[str, str]) -> None:
        self.vault_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def set_secret(self, name: str, value: str) -> dict[str, Any]:
        key = name.strip()
        if not key:
            return {"ok": False, "message": "name is required"}
        vault = self._read_vault()
        vault[key] = protect_text(value)
        self._write_vault(vault)
        return {"ok": True, "name": key}

    def get_secret(self, name: str, reveal: bool = False) -> dict[str, Any]:
        key = name.strip()
        vault = self._read_vault()
        if key not in vault:
            return {"ok": False, "message": f"secret not found: {key}"}
        plain = unprotect_text(vault[key])
        if reveal:
            return {"ok": True, "name": key, "value": plain}
        masked = plain[:2] + "*" * max(0, len(plain) - 4) + plain[-2:] if len(plain) > 4 else "****"
        return {"ok": True, "name": key, "value": masked}

    def delete_secret(self, name: str) -> dict[str, Any]:
        key = name.strip()
        vault = self._read_vault()
        if key not in vault:
            return {"ok": False, "message": f"secret not found: {key}"}
        del vault[key]
        self._write_vault(vault)
        return {"ok": True, "name": key}

    def list_secrets(self) -> dict[str, Any]:
        vault = self._read_vault()
        return {"ok": True, "secrets": sorted(vault.keys())}

    def set_oauth_token(self, provider: str, access_token: str, refresh_token: str = "", expires_at: str = "") -> dict[str, Any]:
        payload = {
            "provider": provider,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.set_secret(f"oauth:{provider}", json.dumps(payload))

    def get_oauth_token(self, provider: str, reveal: bool = False) -> dict[str, Any]:
        out = self.get_secret(f"oauth:{provider}", reveal=True)
        if not out.get("ok"):
            return out
        try:
            payload = json.loads(str(out.get("value", "{}")))
        except json.JSONDecodeError:
            return {"ok": False, "message": "stored oauth payload is invalid"}

        if not reveal:
            payload["access_token"] = "***"
            if payload.get("refresh_token"):
                payload["refresh_token"] = "***"

        return {"ok": True, "oauth": payload}

    def _read_policy(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {"version": 1, "default": "deny", "allow": {}}
        if not isinstance(payload, dict):
            payload = {"version": 1, "default": "deny", "allow": {}}
        payload.setdefault("allow", {})
        payload.setdefault("default", "deny")
        return payload

    def set_policy(self, agent: str, actions: list[str]) -> dict[str, Any]:
        payload = self._read_policy()
        allow = payload.get("allow", {})
        if not isinstance(allow, dict):
            allow = {}
        allow[agent] = sorted({a.strip() for a in actions if a.strip()})
        payload["allow"] = allow
        self.policy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "agent": agent, "actions": allow[agent]}

    def check_policy(self, agent: str, action: str) -> dict[str, Any]:
        payload = self._read_policy()
        allow = payload.get("allow", {}) if isinstance(payload.get("allow"), dict) else {}
        allowed = allow.get(agent, []) if isinstance(allow.get(agent), list) else []
        ok = "*" in allowed or action in allowed
        return {"ok": True, "agent": agent, "action": action, "allowed": ok}

    def scan_workspace(self, path: str = "") -> dict[str, Any]:
        target = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
        if not target.exists():
            return {"ok": False, "message": f"path not found: {target}"}

        findings: list[dict[str, Any]] = []
        total_files = 0
        for file in target.rglob("*"):
            if not file.is_file():
                continue
            if file.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe", ".dll", ".pyd", ".zip"}:
                continue
            total_files += 1
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    findings.append(
                        {
                            "file": str(file),
                            "pattern": pattern.pattern,
                            "snippet": match.group(0)[:80],
                        }
                    )
                    if len(findings) >= 250:
                        break
                if len(findings) >= 250:
                    break

        high = len(findings)
        status = "clean" if high == 0 else ("warning" if high < 10 else "critical")
        return {
            "ok": True,
            "path": str(target),
            "files_scanned": total_files,
            "findings": findings,
            "status": status,
        }

    def handle_command(self, payload: dict[str, Any]) -> None:
        if payload.get("target") not in {"security_sentinel", "security"}:
            return

        command = str(payload.get("command", ""))
        args = payload.get("args") or {}

        if command == "status_ping":
            result = {"ok": True, "status": "alive"}
        elif command == "scan_workspace":
            result = self.scan_workspace(str(args.get("path", "")))
        elif command == "set_secret":
            result = self.set_secret(str(args.get("name", "")), str(args.get("value", "")))
        elif command == "get_secret":
            result = self.get_secret(str(args.get("name", "")), bool(args.get("reveal", False)))
        elif command == "delete_secret":
            result = self.delete_secret(str(args.get("name", "")))
        elif command == "list_secrets":
            result = self.list_secrets()
        elif command == "set_oauth_token":
            result = self.set_oauth_token(
                provider=str(args.get("provider", "")),
                access_token=str(args.get("access_token", "")),
                refresh_token=str(args.get("refresh_token", "")),
                expires_at=str(args.get("expires_at", "")),
            )
        elif command == "get_oauth_token":
            result = self.get_oauth_token(str(args.get("provider", "")), bool(args.get("reveal", False)))
        elif command == "set_policy":
            actions = args.get("actions") if isinstance(args.get("actions"), list) else []
            result = self.set_policy(str(args.get("agent", "")), [str(a) for a in actions])
        elif command == "check_policy":
            result = self.check_policy(str(args.get("agent", "")), str(args.get("action", "")))
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("security_sentinel", f"command:{command}", result)
        self.bus.write_state("security_sentinel", {"service": "security_sentinel", "pid": os.getpid(), "last_command": command, **result})

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            self.bus.write_state(
                "security_sentinel",
                {
                    "service": "security_sentinel",
                    "pid": os.getpid(),
                    "status": "idle",
                },
            )
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
            time.sleep(self.interval_seconds)

    def run_forever(self) -> None:
        self.run(stop_event=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS Security Sentinel agent")
    parser.add_argument("--interval", type=int, default=20)
    args = parser.parse_args()

    agent = SecuritySentinelAgent(interval_seconds=args.interval)
    agent.run_forever()


if __name__ == "__main__":
    main()
