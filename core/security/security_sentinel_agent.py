import argparse
import json
import os
import re
import signal
import subprocess
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


STABILITY_PROFILES: dict[str, dict[str, Any]] = {
    "low_end": {
        "monitor_duplicates": True,
        "auto_kill_duplicate_launchers": True,
        "max_launcher_instances": 1,
        "monitor_memory": True,
        "min_available_memory_mb": 2048,
        "offline_targets_on_pressure": ["voice_daemon", "speaker", "model_gateway"],
        "monitor_os_snapshot": True,
        "snapshot_danger_keywords": ["critical", "high"],
        "offline_targets_on_snapshot_danger": ["voice_daemon", "speaker", "model_gateway"],
    },
    "balanced": {
        "monitor_duplicates": True,
        "auto_kill_duplicate_launchers": True,
        "max_launcher_instances": 1,
        "monitor_memory": True,
        "min_available_memory_mb": 1024,
        "offline_targets_on_pressure": ["voice_daemon", "speaker"],
        "monitor_os_snapshot": True,
        "snapshot_danger_keywords": ["critical", "high"],
        "offline_targets_on_snapshot_danger": ["voice_daemon", "speaker"],
    },
    "high_end": {
        "monitor_duplicates": True,
        "auto_kill_duplicate_launchers": True,
        "max_launcher_instances": 1,
        "monitor_memory": True,
        "min_available_memory_mb": 768,
        "offline_targets_on_pressure": ["voice_daemon"],
        "monitor_os_snapshot": True,
        "snapshot_danger_keywords": ["critical"],
        "offline_targets_on_snapshot_danger": ["voice_daemon"],
    },
}


class SecuritySentinelAgent:
    def __init__(self, interval_seconds: int = 20, root: Path | None = None) -> None:
        self.interval_seconds = interval_seconds
        self.bus = RuneBus(root or resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.vault_path = self.bus.state / "security_secrets_vault.json"
        self.policy_path = self.bus.state / "security_policy.json"
        self._offline_cooldown_seconds = 120
        self._last_offline_at: dict[str, float] = {}
        self._last_voice_status_report_at = 0.0
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
            "stability": {
                "monitor_duplicates": True,
                "auto_kill_duplicate_launchers": True,
                "max_launcher_instances": 1,
                "monitor_memory": True,
                "min_available_memory_mb": 1024,
                "offline_targets_on_pressure": ["voice_daemon", "speaker"],
                "monitor_os_snapshot": True,
                "snapshot_danger_keywords": ["critical", "high"],
                "offline_targets_on_snapshot_danger": ["voice_daemon", "speaker"],
                "monitor_process_recommendations": True,
                "process_memory_threshold_mb": 350,
                "max_process_recommendations": 4,
                "voice_status_report_cooldown_seconds": 300,
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
        if not isinstance(payload.get("stability"), dict):
            payload["stability"] = {}
        return payload

    def _stability_config(self) -> dict[str, Any]:
        payload = self._read_policy()
        cfg = payload.get("stability") if isinstance(payload.get("stability"), dict) else {}
        return {
            "monitor_duplicates": bool(cfg.get("monitor_duplicates", True)),
            "auto_kill_duplicate_launchers": bool(cfg.get("auto_kill_duplicate_launchers", True)),
            "max_launcher_instances": max(1, int(cfg.get("max_launcher_instances", 1) or 1)),
            "monitor_memory": bool(cfg.get("monitor_memory", True)),
            "min_available_memory_mb": max(256, int(cfg.get("min_available_memory_mb", 1024) or 1024)),
            "offline_targets_on_pressure": [str(x) for x in cfg.get("offline_targets_on_pressure", ["voice_daemon", "speaker"]) if str(x).strip()],
            "monitor_os_snapshot": bool(cfg.get("monitor_os_snapshot", True)),
            "snapshot_danger_keywords": [str(x).strip().lower() for x in cfg.get("snapshot_danger_keywords", ["critical", "high"]) if str(x).strip()],
            "offline_targets_on_snapshot_danger": [str(x) for x in cfg.get("offline_targets_on_snapshot_danger", ["voice_daemon", "speaker"]) if str(x).strip()],
            "monitor_process_recommendations": bool(cfg.get("monitor_process_recommendations", True)),
            "process_memory_threshold_mb": max(128, int(cfg.get("process_memory_threshold_mb", 350) or 350)),
            "max_process_recommendations": max(1, int(cfg.get("max_process_recommendations", 4) or 4)),
            "voice_status_report_cooldown_seconds": max(60, int(cfg.get("voice_status_report_cooldown_seconds", 300) or 300)),
        }

    def set_stability_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self._read_policy()
        cfg = payload.get("stability") if isinstance(payload.get("stability"), dict) else {}
        cfg.update({k: v for k, v in updates.items() if k in {
            "monitor_duplicates",
            "auto_kill_duplicate_launchers",
            "max_launcher_instances",
            "monitor_memory",
            "min_available_memory_mb",
            "offline_targets_on_pressure",
            "monitor_os_snapshot",
            "snapshot_danger_keywords",
            "offline_targets_on_snapshot_danger",
            "monitor_process_recommendations",
            "process_memory_threshold_mb",
            "max_process_recommendations",
            "voice_status_report_cooldown_seconds",
        }})
        payload["stability"] = cfg
        self.policy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "stability": self._stability_config()}

    def _recommended_process_candidates(self, threshold_mb: int, max_items: int) -> list[dict[str, Any]]:
        try:
            import psutil  # type: ignore
        except Exception:
            return []

        ignore_names = {
            "system",
            "registry",
            "smss.exe",
            "csrss.exe",
            "wininit.exe",
            "services.exe",
            "lsass.exe",
            "svchost.exe",
            "dwm.exe",
            "explorer.exe",
        }
        avoid_terms = {
            "bossforge_launcher.py",
            "security_sentinel_agent.py",
            "voice_daemon.py",
            "speaker_daemon.py",
            "runeforge_agent.py",
            "model_gateway_agent.py",
            "archivist_agent.py",
            "codemage_agent.py",
            "devlot_agent.py",
            "hearth_tender_daemon.py",
            "test_sentinel_agent.py",
        }

        candidates: list[dict[str, Any]] = []
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                info = proc.info or {}
                pid = int(info.get("pid", 0) or 0)
                if pid <= 0 or pid == os.getpid():
                    continue

                name = str(info.get("name") or "").lower()
                if not name or name in ignore_names:
                    continue

                try:
                    cmdline_items = proc.cmdline()
                    cmdline = " ".join(str(x) for x in cmdline_items) if isinstance(cmdline_items, list) else str(cmdline_items)
                except Exception:
                    cmdline = ""
                cmdline_l = cmdline.lower()
                if any(term in cmdline_l for term in avoid_terms):
                    continue

                try:
                    rss_mb = int((proc.memory_info().rss or 0) / (1024 * 1024))
                except Exception:
                    continue

                if rss_mb < threshold_mb:
                    continue

                # Favor user-facing background apps commonly safe to close first.
                priority = 0
                if any(x in name for x in ["chrome", "msedge", "firefox", "discord", "teams", "spotify", "steam", "epic", "obs", "onedrive"]):
                    priority += 2
                if any(x in name for x in ["helper", "updater", "launcher"]):
                    priority += 1

                candidates.append(
                    {
                        "pid": pid,
                        "name": name,
                        "rss_mb": rss_mb,
                        "priority": priority,
                        "commandline": cmdline[:280],
                    }
                )
            except Exception:
                continue

        ranked = sorted(candidates, key=lambda item: (item.get("priority", 0), item.get("rss_mb", 0)), reverse=True)
        return ranked[:max_items]

    def process_recommendations(self, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
        local_cfg = cfg or self._stability_config()
        threshold_mb = int(local_cfg.get("process_memory_threshold_mb", 350))
        max_items = int(local_cfg.get("max_process_recommendations", 4))
        candidates = self._recommended_process_candidates(threshold_mb=threshold_mb, max_items=max_items)

        recs = [
            {
                "name": item.get("name", "process"),
                "pid": int(item.get("pid", 0) or 0),
                "rss_mb": int(item.get("rss_mb", 0) or 0),
                "recommendation": "Consider closing if not currently needed to reduce memory pressure.",
            }
            for item in candidates
        ]
        return {
            "ok": True,
            "threshold_mb": threshold_mb,
            "recommendations": recs,
            "count": len(recs),
        }

    def _emit_runeforge_status_report(self, snapshot: dict[str, Any], process_recs: dict[str, Any], force: bool = False) -> dict[str, Any]:
        cfg = self._stability_config()
        cooldown = int(cfg.get("voice_status_report_cooldown_seconds", 300))
        now = time.monotonic()
        if not force and (now - self._last_voice_status_report_at) < cooldown:
            return {"ok": True, "skipped": "cooldown", "seconds_remaining": int(cooldown - (now - self._last_voice_status_report_at))}

        warnings = snapshot.get("warnings") if isinstance(snapshot.get("warnings"), list) else []
        warnings_text = [str(w).strip() for w in warnings if str(w).strip()]
        recs = process_recs.get("recommendations") if isinstance(process_recs.get("recommendations"), list) else []

        parts: list[str] = []
        parts.append("Security Sentinel status report.")
        if warnings_text:
            parts.append("System warnings: " + "; ".join(warnings_text[:2]) + ".")
        else:
            parts.append("No active hardware pressure warnings.")

        if recs:
            top = recs[:3]
            top_text = "; ".join(f"{str(item.get('name','process')).replace('.exe','')} using {int(item.get('rss_mb',0))} megabytes" for item in top)
            parts.append("Sentinel recommends closing: " + top_text + ".")
        else:
            parts.append("No unnecessary high-memory background processes detected right now.")

        msg = " ".join(parts)
        self.bus.emit_event("runeforge", "voice_feedback", {"message": msg}, level="warning" if recs else "info")
        self.bus.emit_event(
            "security_sentinel",
            "status_report_to_runeforge",
            {
                "message": msg,
                "warnings": warnings_text,
                "recommendations": recs,
            },
            level="warning" if recs else "info",
        )
        self._last_voice_status_report_at = now
        return {"ok": True, "broadcast": True, "message": msg}

    def apply_stability_profile(self, profile: str) -> dict[str, Any]:
        key = profile.strip().lower()
        if key not in STABILITY_PROFILES:
            return {
                "ok": False,
                "message": f"unknown profile: {profile}",
                "available_profiles": sorted(STABILITY_PROFILES.keys()),
            }
        updates = dict(STABILITY_PROFILES[key])
        result = self.set_stability_policy(updates)
        result["profile"] = key
        return result

    def _load_hearth_snapshot(self) -> dict[str, Any]:
        path = self.bus.state / "hearth_tender.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _os_snapshot_danger(self, snapshot: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
        warnings = snapshot.get("warnings") if isinstance(snapshot.get("warnings"), list) else []
        warning_texts = [str(w).strip() for w in warnings if str(w).strip()]
        lowered = [w.lower() for w in warning_texts]
        hits = [w for w in warning_texts if any(k in w.lower() for k in keywords)]
        return {
            "danger": bool(hits),
            "warnings": warning_texts,
            "matched_warnings": hits,
            "warning_count": len(lowered),
        }

    def _maybe_offline_targets(self, targets: list[str], reason: str, hard: bool) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        now = time.monotonic()
        for target in targets:
            key = str(target).strip().lower()
            if not key:
                continue
            last = float(self._last_offline_at.get(key, 0.0))
            if now - last < self._offline_cooldown_seconds:
                actions.append({"ok": True, "agent": key, "skipped": "cooldown", "seconds_remaining": int(self._offline_cooldown_seconds - (now - last))})
                continue
            result = self.offline_agent(agent=key, reason=reason, hard=hard)
            self._last_offline_at[key] = now
            actions.append(result)
        return actions

    def _python_processes(self) -> list[dict[str, Any]]:
        try:
            import psutil  # type: ignore

            out: list[dict[str, Any]] = []
            for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
                info = proc.info or {}
                name = str(info.get("name") or "").lower()
                if name not in {"python", "python.exe", "pythonw", "pythonw.exe"}:
                    continue
                cmdline_items = info.get("cmdline") or []
                if isinstance(cmdline_items, list):
                    cmdline = " ".join(str(x) for x in cmdline_items)
                else:
                    cmdline = str(cmdline_items)
                pid = int(info.get("pid", 0) or 0)
                if pid > 0:
                    out.append({"pid": pid, "commandline": cmdline})
            return out
        except Exception:
            pass

        if os.name != "nt":
            return []

        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match '^python(\\.exe)?$|^pythonw(\\.exe)?$' } | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress",
        ]
        try:
            raw = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=10).strip()
        except Exception:
            return []
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        items = parsed if isinstance(parsed, list) else [parsed]
        out: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = int(item.get("ProcessId", 0) or 0)
            cmdline = str(item.get("CommandLine", "") or "")
            if pid > 0:
                out.append({"pid": pid, "commandline": cmdline})
        return out

    def _kill_pid(self, pid: int) -> dict[str, Any]:
        if pid <= 0:
            return {"ok": False, "pid": pid, "message": "invalid pid"}
        if pid == os.getpid():
            return {"ok": False, "pid": pid, "message": "refusing to terminate own process"}

        try:
            import psutil  # type: ignore

            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
                proc.wait(timeout=3)
            return {"ok": True, "pid": pid}
        except Exception:
            pass

        if os.name != "nt":
            try:
                os.kill(pid, signal.SIGTERM)
                return {"ok": True, "pid": pid}
            except Exception as ex:
                return {"ok": False, "pid": pid, "message": str(ex)}

        try:
            subprocess.check_output(["taskkill", "/PID", str(pid), "/F"], text=True, stderr=subprocess.STDOUT, timeout=8)
            return {"ok": True, "pid": pid}
        except Exception as ex:
            return {"ok": False, "pid": pid, "message": str(ex)}

    def _available_memory_mb(self) -> int:
        try:
            import psutil  # type: ignore

            return int(psutil.virtual_memory().available / (1024 * 1024))
        except Exception:
            return -1

    def offline_agent(self, agent: str, reason: str = "stability pressure", hard: bool = False) -> dict[str, Any]:
        target = agent.strip().lower()
        if not target:
            return {"ok": False, "message": "agent is required"}

        if hard and target in {"voice_daemon", "speaker"}:
            self.bus.emit_command(target=target, command="stop", args={"reason": reason}, issued_by="security_sentinel")
            mode = "hard-stop"
        else:
            mode = "policy-offline"

        policy_result = self.set_policy(target, [])
        result = {
            "ok": True,
            "agent": target,
            "reason": reason,
            "mode": mode,
            "policy": policy_result,
        }
        self.bus.emit_event("security_sentinel", "stability:offline_agent", result, level="warning")
        return result

    def monitor_stability(self) -> dict[str, Any]:
        cfg = self._stability_config()
        actions: list[dict[str, Any]] = []
        process_recs = {"ok": True, "recommendations": [], "count": 0}

        if cfg["monitor_duplicates"]:
            processes = self._python_processes()
            launchers = [
                proc for proc in processes
                if "bossforge_launcher.py" in proc.get("commandline", "").lower()
            ]
            launchers = sorted(launchers, key=lambda item: int(item.get("pid", 0)))
            duplicate_count = max(0, len(launchers) - int(cfg["max_launcher_instances"]))
            if duplicate_count > 0:
                keep_pids = {os.getpid()}
                for proc in launchers:
                    pid = int(proc.get("pid", 0) or 0)
                    if pid <= 0 or pid in keep_pids:
                        continue
                    if len(launchers) - len(keep_pids) <= int(cfg["max_launcher_instances"]):
                        break
                    if cfg["auto_kill_duplicate_launchers"]:
                        kill_result = self._kill_pid(pid)
                        actions.append({"type": "kill_duplicate_launcher", **kill_result})
                    else:
                        actions.append({"type": "duplicate_launcher_detected", "pid": pid, "ok": False})

        if cfg["monitor_memory"]:
            available_mb = self._available_memory_mb()
            threshold = int(cfg["min_available_memory_mb"])
            if available_mb >= 0 and available_mb < threshold:
                pressure_actions = self._maybe_offline_targets(
                    targets=cfg["offline_targets_on_pressure"],
                    reason=f"available_memory_mb={available_mb} below threshold={threshold}",
                    hard=True,
                )
                for item in pressure_actions:
                    actions.append({"type": "offline_on_memory_pressure", **item})

        snapshot = self._load_hearth_snapshot()
        if cfg["monitor_os_snapshot"] and snapshot:
            danger = self._os_snapshot_danger(snapshot, cfg["snapshot_danger_keywords"])
            if danger["danger"]:
                snapshot_actions = self._maybe_offline_targets(
                    targets=cfg["offline_targets_on_snapshot_danger"],
                    reason=f"os_snapshot_danger={'; '.join(danger['matched_warnings'])}",
                    hard=True,
                )
                for item in snapshot_actions:
                    actions.append({"type": "offline_on_snapshot_danger", **item, "snapshot": danger})

        if cfg["monitor_process_recommendations"]:
            process_recs = self.process_recommendations(cfg)
            recs = process_recs.get("recommendations") if isinstance(process_recs.get("recommendations"), list) else []
            if recs:
                actions.append({"type": "process_close_recommendations", "count": len(recs), "recommendations": recs})
                if snapshot:
                    voice_out = self._emit_runeforge_status_report(snapshot=snapshot, process_recs=process_recs, force=False)
                    actions.append({"type": "runeforge_voice_report", **voice_out})

        status = "stable" if not actions else "mitigated"
        result = {
            "ok": True,
            "status": status,
            "actions": actions,
            "config": cfg,
            "snapshot_checked": bool(snapshot),
            "process_recommendations": process_recs,
        }
        if actions:
            self.bus.emit_event("security_sentinel", "stability:actions", result, level="warning")
        return result

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
        elif command == "monitor_stability":
            result = self.monitor_stability()
        elif command == "set_stability_policy":
            updates = args if isinstance(args, dict) else {}
            result = self.set_stability_policy(updates)
        elif command == "apply_stability_profile":
            result = self.apply_stability_profile(str(args.get("profile", "balanced")))
        elif command == "offline_agent":
            result = self.offline_agent(
                agent=str(args.get("agent", "")),
                reason=str(args.get("reason", "manual")),
                hard=bool(args.get("hard", False)),
            )
        elif command == "process_recommendations":
            result = self.process_recommendations()
        elif command == "broadcast_status_report":
            snapshot = self._load_hearth_snapshot()
            process_recs = self.process_recommendations()
            result = self._emit_runeforge_status_report(snapshot=snapshot, process_recs=process_recs, force=True)
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}

        self.bus.emit_event("security_sentinel", f"command:{command}", result)
        self.bus.write_state("security_sentinel", {"service": "security_sentinel", "pid": os.getpid(), "last_command": command, **result})

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            stability = self.monitor_stability()
            self.bus.write_state(
                "security_sentinel",
                {
                    "service": "security_sentinel",
                    "pid": os.getpid(),
                    "status": "idle",
                    "stability": stability,
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
