import argparse
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib import error, request
from urllib.parse import urlparse
import hashlib

from core.connectors.bossgate_connector import (
    apply_metadata_visibility_profile,
    build_transfer_resume_plan,
    build_transfer_envelope,
    decrypt_json_payload,
    discover_transfer_targets,
    encrypt_json_payload,
    generate_secure_address,
    is_valid_secure_address,
    scan_rest_endpoints,
    validate_transfer_envelope,
)
from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.security.bossgate_authorization import BossGateAuthorizationRegistry

SUPER_GATE_TARGET_TYPES = {"bridgebase_alpha", "ass", "bossforgeos"}


class BossGateCommandAgent:
    def __init__(self, interval_seconds: int = 5, root: Path | None = None) -> None:
        self.interval_seconds = max(1, int(interval_seconds))
        self.bus = RuneBus(root or resolve_root_from_env())
        self.seen_commands: set[str] = set()
        self.node_id_path = self.bus.state / "bossgate_node_id.txt"
        self.profiles_path = self.bus.state / "model_profiles.json"
        self.packages_dir = self.bus.state / "bossgate_packages"
        self.licenses_dir = self.bus.state / "bossgate_licenses"
        self.interface_maps_dir = self.bus.state / "bossgate_interface_maps"
        self.remote_debug_sessions_path = self.bus.state / "bossgate_remote_debug_sessions.json"
        self.remote_debug_transcripts_path = self.bus.state / "bossgate_remote_debug_transcripts.jsonl"
        self.transfer_log_path = self.bus.state / "bossgate_transfers.jsonl"
        self.keyring_path = self.bus.state / "bossgate_keys.json"
        self.replay_tokens_path = self.bus.state / "bossgate_replay_tokens.json"
        self.node_profile_path = self.bus.state / "bossgate_node_profile.json"
        self.map_path = self.bus.state / "bossgate_map.json"
        self.authorization_registry = BossGateAuthorizationRegistry(self.bus.state / "bossgate_human_roles.json")
        self.node_id = self._load_or_create_node_id()
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.licenses_dir.mkdir(parents=True, exist_ok=True)
        self.interface_maps_dir.mkdir(parents=True, exist_ok=True)
        self._keyring = self._load_or_create_keyring()
        self._replay_tokens = self._load_replay_tokens()
        self._node_profile = self._load_or_create_node_profile()
        self._last_map_refresh_ts = 0.0

    def _new_correlation_id(self, action: str) -> str:
        safe_action = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "-" for ch in str(action).strip().lower())
        return f"bg-{safe_action}-{self.node_id}-{int(time.time() * 1000)}"

    def _emit_lifecycle_event(
        self,
        action: str,
        correlation_id: str,
        result: Dict[str, Any],
        **context: Any,
    ) -> None:
        payload: Dict[str, Any] = {
            "correlation_id": correlation_id,
            "action": action,
            "ok": bool(result.get("ok", False)),
            "status": str(result.get("status", "ok" if result.get("ok", False) else "failed")),
        }
        payload.update(context)
        payload.update(result)
        self.bus.emit_event("bossgate", f"lifecycle:{action}", payload, level="info" if payload["ok"] else "warning")

    def _append_transfer_ledger(self, **record: Any) -> None:
        entry = {
            "record_type": "bossgate_transfer_ledger_v1",
            "schema_version": 1,
            "timestamp": int(time.time()),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        entry.update(record)
        with self.transfer_log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, separators=(",", ":")))
            fp.write("\n")

    def _deny(
        self,
        reason_code: str,
        message: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": False,
            "message": message,
            "reason_code": str(reason_code).strip(),
            "reason_codes": [str(reason_code).strip()],
        }
        payload.update(extra)
        return payload

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

    def _load_agent_profiles(self) -> Dict[str, Dict[str, Any]]:
        if not self.profiles_path.exists():
            return {}
        try:
            raw = json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                out[str(k).strip().lower()] = dict(v)
        return out

    def _save_agent_profiles(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        self.profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self.profiles_path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")

    def _load_replay_tokens(self) -> set[str]:
        if not self.replay_tokens_path.exists():
            return set()
        try:
            payload = json.loads(self.replay_tokens_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if not isinstance(payload, dict) or not isinstance(payload.get("tokens"), list):
            return set()
        return {str(token).strip() for token in payload["tokens"] if str(token).strip()}

    def _load_remote_debug_sessions(self) -> dict[str, Any]:
        if not self.remote_debug_sessions_path.exists():
            return {"version": 1, "sessions": {}}
        try:
            payload = json.loads(self.remote_debug_sessions_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "sessions": {}}
        if not isinstance(payload, dict):
            return {"version": 1, "sessions": {}}
        sessions = payload.get("sessions")
        payload["sessions"] = sessions if isinstance(sessions, dict) else {}
        payload.setdefault("version", 1)
        return payload

    def _save_remote_debug_sessions(self, payload: dict[str, Any]) -> None:
        self.remote_debug_sessions_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _append_remote_debug_transcript(self, entry: dict[str, Any]) -> None:
        sanitized = {
            key: value
            for key, value in entry.items()
            if key not in {"session_token", "authorization"}
        }
        with self.remote_debug_transcripts_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitized, sort_keys=True) + "\n")

    def _save_replay_tokens(self) -> None:
        self.replay_tokens_path.write_text(
            json.dumps({"tokens": sorted(self._replay_tokens)}, indent=2),
            encoding="utf-8",
        )

    def _load_or_create_node_profile(self) -> Dict[str, Any]:
        if self.node_profile_path.exists():
            try:
                data = json.loads(self.node_profile_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("node_id", self.node_id)
                    data["target_type"] = str(data.get("target_type", "bossforgeos")).strip().lower() or "bossforgeos"
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        data = {"node_id": self.node_id, "target_type": "bossforgeos"}
        self.node_profile_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def set_node_target_type(self, target_type: str) -> Dict[str, Any]:
        normalized = str(target_type).strip().lower()
        if not normalized:
            return {"ok": False, "message": "target_type is required"}
        self._node_profile["target_type"] = normalized
        self._node_profile["node_id"] = self.node_id
        self.node_profile_path.write_text(json.dumps(self._node_profile, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "node_id": self.node_id,
            "target_type": normalized,
            "travel_initiation_allowed": normalized in SUPER_GATE_TARGET_TYPES,
        }

    def _can_initiate_travel(self) -> tuple[bool, str]:
        target_type = str(self._node_profile.get("target_type", "bossforgeos")).strip().lower() or "bossforgeos"
        return target_type in SUPER_GATE_TARGET_TYPES, target_type

    def _best_effort_secure_delete(self, path: Path) -> None:
        try:
            if not path.exists() or not path.is_file():
                return
            size = path.stat().st_size
            # Best-effort overwrite before unlink to reduce local residue.
            with path.open("r+b") as fp:
                fp.write(b"\x00" * size)
                fp.flush()
            path.unlink(missing_ok=True)
        except Exception:
            pass

    def _retire_local_agent_traces(self, agent_name: str, package_path: Path) -> dict[str, Any]:
        key = str(agent_name).strip().lower()
        removed: dict[str, Any] = {"agent": key, "profile_removed": False, "files_deleted": []}
        if not key:
            return removed

        profiles = self._load_agent_profiles()
        if key in profiles:
            del profiles[key]
            self._save_agent_profiles(profiles)
            removed["profile_removed"] = True

        safe_state = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in key)
        state_candidates = [
            self.bus.state / f"model_agent_{safe_state}.json",
            package_path,
        ]
        for candidate in state_candidates:
            if candidate.exists():
                self._best_effort_secure_delete(candidate)
                removed["files_deleted"].append(str(candidate))
        return removed

    def _load_or_create_keyring(self) -> Dict[str, Any]:
        if self.keyring_path.exists():
            try:
                data = json.loads(self.keyring_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("keys"), dict):
                    data.setdefault("active_key_id", "default")
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        seed = f"{self.node_id}:default"
        data = {"active_key_id": "default", "keys": {"default": seed}}
        self.keyring_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def _save_keyring(self) -> None:
        self.keyring_path.write_text(json.dumps(self._keyring, indent=2), encoding="utf-8")

    def _active_key_id(self) -> str:
        return str(self._keyring.get("active_key_id", "default")).strip() or "default"

    def _resolve_encrypt_key(self, override: str = "") -> tuple[str, str]:
        if override.strip():
            return "override", override.strip()
        active = self._active_key_id()
        keys = self._keyring.get("keys") if isinstance(self._keyring.get("keys"), dict) else {}
        key_val = str(keys.get(active, "")).strip()
        if not key_val:
            key_val = str(keys.get("default", "")).strip()
            active = "default"
        return active, key_val or self.node_id

    def _decrypt_keyring(self, override: str = "") -> dict[str, str]:
        if override.strip():
            return {"default": override.strip(), "override": override.strip()}
        keys = self._keyring.get("keys") if isinstance(self._keyring.get("keys"), dict) else {}
        out: dict[str, str] = {}
        for k, v in keys.items():
            key_id = str(k).strip()
            key_val = str(v).strip()
            if key_id and key_val:
                out[key_id] = key_val
        if "default" not in out:
            out["default"] = self.node_id
        return out

    def rotate_key(
        self,
        new_key_id: str = "",
        new_secret_key: str = "",
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("rotate_key")
        authorized, authorization = self._require_authorization(
            operator_id=operator_id,
            scope_id=scope_id,
            permission="bossgate.key.rotate",
            actor_type=actor_type,
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("rotate_key", correlation_id, authorization)
            return authorization
        key_id = str(new_key_id).strip() or f"k{int(time.time())}"
        secret = str(new_secret_key).strip() or f"{self.node_id}:{key_id}:{int(time.time())}"
        keys = self._keyring.get("keys") if isinstance(self._keyring.get("keys"), dict) else {}
        keys[key_id] = secret
        self._keyring["keys"] = keys
        self._keyring["active_key_id"] = key_id
        self._save_keyring()
        result = {
            "ok": True,
            "active_key_id": key_id,
            "key_count": len(keys),
            "authorization": authorization,
            "correlation_id": correlation_id,
            "status": "key_rotated",
        }
        self._emit_lifecycle_event("rotate_key", correlation_id, result)
        return result

    def _require_authorization(
        self,
        operator_id: str = "",
        scope_id: str = "",
        permission: str = "",
        actor_type: str = "human",
        required_agent_skill: str = "",
    ) -> tuple[bool, dict[str, str] | Dict[str, Any]]:
        normalized_actor_type = str(actor_type or "human").strip().lower() or "human"
        authorization = {
            "operator_id": str(operator_id).strip(),
            "scope_id": str(scope_id).strip(),
            "actor_type": normalized_actor_type,
        }
        if not authorization["operator_id"] or not authorization["scope_id"]:
            return False, self._deny(
                "missing_authorization_context",
                "authorization denied: operator_id and scope_id are required",
                authorization=authorization,
            )
        if normalized_actor_type == "agent":
            profiles = self._load_agent_profiles()
            profile = profiles.get(authorization["operator_id"].lower())
            if not isinstance(profile, dict):
                return False, self._deny(
                    "unknown_agent",
                    f"authorization denied: unknown agent: {authorization['operator_id']}",
                    authorization=authorization,
                )
            skills = {str(item).strip().lower() for item in profile.get("skills", []) if str(item).strip()} if isinstance(profile.get("skills"), list) else set()
            if required_agent_skill and required_agent_skill not in skills:
                return False, self._deny(
                    "missing_agent_skill",
                    f"authorization denied: agent skill is required: {required_agent_skill}",
                    authorization=authorization,
                )
            return True, authorization
        if normalized_actor_type != "human":
            return False, self._deny(
                "unknown_actor_type",
                f"authorization denied: unknown actor_type: {normalized_actor_type}",
                authorization=authorization,
            )
        if not self.authorization_registry.roles_for_user(authorization["operator_id"]):
            return False, self._deny(
                "unknown_operator",
                f"authorization denied: unknown operator: {authorization['operator_id']}",
                authorization=authorization,
            )
        if permission and not self.authorization_registry.has_permission(authorization["operator_id"], permission):
            return False, self._deny(
                "missing_permission",
                f"authorization denied: permission is required: {permission}",
                authorization=authorization,
            )
        return True, authorization

    def discover_targets(
        self,
        timeout: int = 5,
        assistance_only: bool = False,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("discover_targets")
        authorized, authorization = self._require_authorization(operator_id, scope_id, "bossgate.discovery.run", actor_type)
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
            return authorization
        safe_timeout = max(1, int(timeout))
        targets = discover_transfer_targets(timeout=safe_timeout, assistance_only=bool(assistance_only))
        return {
            "ok": True,
            "timeout": safe_timeout,
            "assistance_only": bool(assistance_only),
            "targets": targets,
            "policy": "travel_allowed_only_to_bossgate_ass_bossforgeos_bridgebase_alpha",
            "authorization": authorization,
            "correlation_id": correlation_id,
        }

    def refresh_map(self, timeout: int = 2) -> Dict[str, Any]:
        safe_timeout = max(1, int(timeout))
        discovered = discover_transfer_targets(timeout=safe_timeout, assistance_only=False)
        gates: dict[str, dict[str, Any]] = {}
        agents: dict[str, dict[str, Any]] = {}

        for item in discovered:
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id", "")).strip()
            address = str(item.get("address", "")).strip()
            if not node_id and not address:
                continue
            gate_key = f"{node_id}|{address}"
            gate = gates.get(gate_key, {})
            gate["node_id"] = node_id
            gate["address"] = address
            gate["target_type"] = str(item.get("target_type", "bossgate_connector")).strip().lower() or "bossgate_connector"
            gate["travelable"] = bool(item.get("allowed_for_transfer", False))
            gate["last_seen"] = int(time.time())
            gates[gate_key] = gate

            agent_name = str(item.get("agent_name", "")).strip().lower()
            if agent_name:
                agents[agent_name] = {
                    "agent_name": agent_name,
                    "node_id": node_id,
                    "address": address,
                    "target_type": gate["target_type"],
                    "travelable_gate": bool(gate["travelable"]),
                    "current_node": str(item.get("current_node", node_id)).strip() or node_id,
                    "created_by_node": str(item.get("created_by_node", "")).strip(),
                    "agent_class": str(item.get("agent_class", "prime")).strip().lower() or "prime",
                    "assistance_requested": bool(item.get("assistance_requested", False)),
                    "assistance_reason": str(item.get("assistance_reason", "")).strip(),
                }

        out = {
            "ok": True,
            "node_id": self.node_id,
            "generated_at": int(time.time()),
            "gates": sorted(gates.values(), key=lambda x: (str(x.get("node_id", "")), str(x.get("address", "")))),
            "travelable_gates": sorted(
                [g for g in gates.values() if bool(g.get("travelable", False))],
                key=lambda x: (str(x.get("node_id", "")), str(x.get("address", ""))),
            ),
            "agents": sorted(agents.values(), key=lambda x: str(x.get("agent_name", ""))),
        }
        self.map_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        self._last_map_refresh_ts = time.time()
        return out

    def map_snapshot(self, refresh: bool = False, timeout: int = 2) -> Dict[str, Any]:
        if refresh or not self.map_path.exists():
            return self.refresh_map(timeout=timeout)
        try:
            data = json.loads(self.map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.refresh_map(timeout=timeout)
        if not isinstance(data, dict):
            return self.refresh_map(timeout=timeout)
        data.setdefault("ok", True)
        return data

    def scan_target(
        self,
        destination: str,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
        internal: bool = False,
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("scan_target")
        authorization: dict[str, Any] = {}
        if not internal:
            authorized, authorization = self._require_authorization(operator_id, scope_id, "bossgate.discovery.run", actor_type)
            if not authorized:
                if isinstance(authorization, dict):
                    authorization = {**authorization, "correlation_id": correlation_id}
                return authorization
        target = destination.strip()
        if not target:
            return self._deny(
                "missing_destination",
                "destination is required",
                allowed_for_transfer=False,
                correlation_id=correlation_id,
            )
        result = scan_rest_endpoints(target)
        if not isinstance(result, dict):
            return self._deny(
                "invalid_target_validation_result",
                "invalid transfer validation result",
                allowed_for_transfer=False,
                destination=target,
                correlation_id=correlation_id,
            )
        result.setdefault("destination", target)
        result.setdefault("authorization", authorization)
        result.setdefault("correlation_id", correlation_id)
        return result

    def build_interface_map(
        self,
        destination: str,
        timeout: int = 2,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("build_interface_map")
        authorized, authorization = self._require_authorization(operator_id, scope_id, "bossgate.discovery.run", actor_type)
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
            return authorization

        target = str(destination).strip()
        if not target:
            return self._deny("missing_destination", "destination is required", correlation_id=correlation_id)

        safe_timeout = max(1, int(timeout))
        discovered = discover_transfer_targets(timeout=safe_timeout, assistance_only=False)
        scanned = self.scan_target(target, internal=True)
        if not scanned.get("ok"):
            if "correlation_id" not in scanned:
                scanned["correlation_id"] = correlation_id
            scanned.setdefault("authorization", authorization)
            return scanned

        parsed = urlparse(str(scanned.get("base_url", target)).strip())
        hostname = (parsed.hostname or "").strip().lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        normalized_base = str(scanned.get("base_url", target)).strip().lower().rstrip("/")

        discovery_matches = []
        for item in discovered:
            if not isinstance(item, dict):
                continue
            address = str(item.get("address", "")).strip().lower().rstrip("/")
            address_host = (urlparse(address).hostname or "").strip().lower() if address else ""
            if address == normalized_base or (hostname and address_host == hostname):
                discovery_matches.append(dict(item))

        documented_endpoints = []
        for endpoint in scanned.get("endpoints", []):
            if not isinstance(endpoint, dict):
                continue
            path = str(endpoint.get("path", "")).strip() or "/"
            methods = sorted(
                {
                    str(method).strip().upper()
                    for method in (endpoint.get("methods") or [])
                    if str(method).strip()
                }
            )
            documented_endpoints.append({"path": path, "methods": methods})
        documented_endpoints.sort(key=lambda item: str(item.get("path", "")))

        protocol_features = {"rest_json"}
        if any(item.get("path") == "/health" for item in documented_endpoints):
            protocol_features.add("health_endpoint")
        if any("transfer" in str(item.get("path", "")).lower() for item in documented_endpoints):
            protocol_features.add("transfer_endpoint")
        metadata = scanned.get("metadata") if isinstance(scanned.get("metadata"), dict) else {}
        if metadata.get("title") or metadata.get("description"):
            protocol_features.add("documented_api")

        slug = "".join(char if char.isalnum() else "-" for char in (hostname or "interface-map")).strip("-") or "interface-map"
        output_path = self.interface_maps_dir / f"{slug}-{port}.json"
        payload = {
            "ok": True,
            "destination": target,
            "base_url": str(scanned.get("base_url", target)).strip(),
            "target_type": str(scanned.get("target_type", "unknown")).strip().lower() or "unknown",
            "allowed_for_transfer": bool(scanned.get("allowed_for_transfer", False)),
            "ports": [int(port)],
            "metadata": metadata,
            "documented_endpoints": documented_endpoints,
            "protocol_features": sorted(protocol_features),
            "discovery_matches": discovery_matches,
            "generated_at": int(time.time()),
            "authorization": authorization,
            "correlation_id": correlation_id,
            "interface_map_file": str(output_path),
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def package_agent(
        self,
        name: str,
        target_system_id: str,
        visibility_profile: str = "none",
        policy_ref: str = "policy/default",
        secret_key: str = "",
        output_file: str = "",
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("package_agent")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.package",
            actor_type,
            required_agent_skill="bossgate_coms_officer",
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("package_agent", correlation_id, authorization, agent_name=str(name).strip().lower())
            return authorization
        profiles = self._load_agent_profiles()
        key = name.strip().lower()
        if not key:
            result = self._deny("missing_agent_name", "name is required", correlation_id=correlation_id)
            self._emit_lifecycle_event("package_agent", correlation_id, result, agent_name=key)
            return result
        profile = profiles.get(key)
        if not isinstance(profile, dict):
            result = self._deny("agent_not_found", f"agent not found: {key}", correlation_id=correlation_id)
            self._emit_lifecycle_event("package_agent", correlation_id, result, agent_name=key)
            return result
        if not bool(profile.get("bossgate_enabled", True)):
            result = self._deny(
                "agent_not_bossgate_enabled",
                f"agent is not bossgate-enabled: {key}",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("package_agent", correlation_id, result, agent_name=key)
            return result
        if not str(target_system_id).strip():
            result = self._deny(
                "missing_target_system_id",
                "target_system_id is required",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("package_agent", correlation_id, result, agent_name=key)
            return result

        secure_address = str(profile.get("secure_address", "")).strip().lower()
        if not is_valid_secure_address(secure_address):
            secure_address = generate_secure_address()
            profile["secure_address"] = secure_address
            profiles[key] = profile
            self._save_agent_profiles(profiles)

        agent_id_card = {
            "agent_id": key,
            "agent_name": key,
            "agent_secure_address": secure_address,
            "publisher": str(profile.get("created_by_node", self.node_id)),
            "build_fingerprint": f"{key}:{str(profile.get('endpoint', ''))}",
            "capabilities_summary": sorted(profile.get("skills", [])) if isinstance(profile.get("skills"), list) else [],
            "license_tier": "prototype",
            "support_contact": "bossgate-operator",
        }
        model_card_snapshot = {
            "model_family": str(profile.get("endpoint", "")),
            "runtime_requirements": {"has_llm": bool(profile.get("has_llm", True))},
            "safety_constraints": ["policy-bound transfer only"],
            "known_limits": ["prototype packaging"],
            "compliance_flags": ["deny_by_default_targets"],
        }
        # AgentForge view posture never grants package-level metadata disclosure.
        metadata = apply_metadata_visibility_profile("none", agent_id_card, model_card_snapshot)
        payload = {
            "agent_name": key,
            "agent_secure_address": secure_address,
            "profile": profile,
            "metadata_visibility": metadata,
            "issuer_node": self.node_id,
            "packaged_at": int(time.time()),
        }
        active_key_id, resolved_secret = self._resolve_encrypt_key(secret_key)
        encrypted_payload = encrypt_json_payload(payload=payload, secret_key=resolved_secret, key_id=active_key_id)
        envelope = build_transfer_envelope(
            agent_id=key,
            agent_version=str(profile.get("version", "1.0.0")),
            issuer=self.node_id,
            target_system_id=str(target_system_id).strip(),
            encrypted_payload=encrypted_payload,
            policy_ref=str(policy_ref).strip() or "policy/default",
            secret_key=resolved_secret,
            expires_in_seconds=1800,
        )
        package_doc = {
            "package_version": 1,
            "agent_name": key,
            "issuer_node": self.node_id,
            "target_system_id": str(target_system_id).strip(),
            "metadata_visibility": metadata,
            "envelope": envelope,
        }
        if output_file.strip():
            package_path = Path(output_file).expanduser().resolve()
            package_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            package_path = self.packages_dir / f"{key}_{int(time.time())}.bossgate.json"
        package_path.write_text(json.dumps(package_doc, indent=2), encoding="utf-8")
        result = {
            "ok": True,
            "agent": key,
            "package_file": str(package_path),
            "target_system_id": str(target_system_id).strip(),
            "visibility_profile": metadata.get("profile", "none"),
            "authorization": authorization,
            "correlation_id": correlation_id,
            "status": "package_created",
        }
        self._emit_lifecycle_event("package_agent", correlation_id, result, agent_name=key)
        return result

    def transfer_agent(
        self,
        package_file: str,
        destination: str,
        dry_run: bool = True,
        resume_from_chunk: int = 0,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("transfer_agent")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.transfer",
            actor_type,
            required_agent_skill="bossgate_travel_control",
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("transfer_agent", correlation_id, authorization, destination=destination)
            return authorization
        can_initiate, node_target_type = self._can_initiate_travel()
        if not can_initiate:
            result = self._deny(
                "travel_initiator_not_super_gate",
                "travel initiation denied: only super gates can initiate travel",
                node_target_type=node_target_type,
                allowed_initiators=sorted(SUPER_GATE_TARGET_TYPES),
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("transfer_agent", correlation_id, result, destination=destination, authorization=authorization)
            return result
        package_path = Path(package_file).expanduser().resolve()
        if not package_path.exists():
            result = self._deny(
                "package_file_not_found",
                f"package file not found: {package_path}",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("transfer_agent", correlation_id, result, destination=destination, authorization=authorization)
            return result
        package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        package_agent_name = str(package_doc.get("agent_name", "")).strip().lower()
        target_validation = self.scan_target(destination, internal=True)
        if not bool(target_validation.get("allowed_for_transfer", False)):
            result = self._deny(
                "target_not_approved_for_transfer",
                "destination is not approved for transfer",
                destination=destination,
                target_validation=target_validation,
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event(
                "transfer_agent",
                correlation_id,
                result,
                authorization=authorization,
                package_file=str(package_path),
                agent_name=package_agent_name,
            )
            return result
        transfer_result: dict[str, Any] = {
            "ok": True,
            "status": "validated_only" if dry_run else "queued_for_transport",
            "http_status": 0,
            "response": {},
        }
        if not dry_run:
            transfer_result = self._send_transfer_package(
                package_path=package_path,
                destination=destination,
                resume_from_chunk=resume_from_chunk,
                correlation_id=correlation_id,
            )
            if not transfer_result.get("ok", False):
                self._append_transfer_ledger(
                    node_id=self.node_id,
                    correlation_id=correlation_id,
                    action="transfer_agent",
                    authorization=authorization,
                    agent_name=package_agent_name,
                    package_file=str(package_path),
                    destination=destination,
                    target_type=str(target_validation.get("target_type", "unknown")),
                    dry_run=False,
                    status="transfer_failed",
                    resume_from_chunk=int(resume_from_chunk),
                    resume_plan=transfer_result.get("resume_plan", {}),
                    error=str(transfer_result.get("message", "")),
                )
                result = self._deny(
                    "transfer_request_failed",
                    str(transfer_result.get("message", "")),
                    destination=destination,
                    package_file=str(package_path),
                    dry_run=False,
                    status="transfer_failed",
                    target_validation=target_validation,
                    authorization=authorization,
                    correlation_id=correlation_id,
                )
                self._emit_lifecycle_event("transfer_agent", correlation_id, result, agent_name=package_agent_name)
                return result
            retirement = self._retire_local_agent_traces(package_agent_name, package_path)
        else:
            retirement = {"agent": package_agent_name, "profile_removed": False, "files_deleted": []}

        record = {
            "node_id": self.node_id,
            "correlation_id": correlation_id,
            "action": "transfer_agent",
            "authorization": authorization,
            "agent_name": package_agent_name,
            "package_file": str(package_path),
            "destination": destination,
            "target_type": str(target_validation.get("target_type", "unknown")),
            "dry_run": bool(dry_run),
            "status": str(transfer_result.get("status", "validated_only" if dry_run else "queued_for_transport")),
            "http_status": int(transfer_result.get("http_status", 0) or 0),
            "resume_from_chunk": int(resume_from_chunk),
            "resume_plan": transfer_result.get("resume_plan", {}),
            "payload_hash": transfer_result.get("payload_hash", ""),
        }
        self._append_transfer_ledger(**record)
        result = {
            "ok": True,
            "destination": destination,
            "package_file": str(package_path),
            "dry_run": bool(dry_run),
            "status": record["status"],
            "http_status": int(transfer_result.get("http_status", 0) or 0),
            "response": transfer_result.get("response", {}),
            "resume_plan": transfer_result.get("resume_plan", {}),
            "move_semantics": {
                "source_retired": bool(not dry_run),
                "retirement": retirement,
            },
            "target_validation": target_validation,
            "authorization": authorization,
            "correlation_id": correlation_id,
        }
        self._emit_lifecycle_event("transfer_agent", correlation_id, result, agent_name=package_agent_name)
        return result

    def _send_transfer_package(
        self,
        package_path: Path,
        destination: str,
        resume_from_chunk: int = 0,
        correlation_id: str = "",
    ) -> dict[str, Any]:
        package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        envelope = package_doc.get("envelope") if isinstance(package_doc, dict) else None
        if not isinstance(envelope, dict):
            return {"ok": False, "message": "package missing envelope", "resume_plan": {}}
        manifest = envelope.get("chunk_manifest")
        chunk_count = int(manifest.get("chunk_count", 0)) if isinstance(manifest, dict) else 0
        safe_resume_from = max(0, int(resume_from_chunk))
        if not isinstance(manifest, dict):
            if safe_resume_from:
                return {"ok": False, "message": "resume requires a package chunk manifest", "resume_plan": {}}
            resume_plan = {}
        else:
            if safe_resume_from > chunk_count:
                return {"ok": False, "message": "resume_from_chunk exceeds package chunk count", "resume_plan": {}}
            resume_plan = build_transfer_resume_plan(envelope, completed_chunk_indexes=list(range(safe_resume_from)))
        correlation_id = correlation_id or self._new_correlation_id("transfer_agent")
        base = destination.rstrip("/")
        endpoint = base + "/bossgate/transfer"
        body = {
            "correlation_id": correlation_id,
            "source_node_id": self.node_id,
            "package_file_name": package_path.name,
            "package": package_doc,
            "resume_plan": resume_plan,
        }
        req = request.Request(
            url=endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                status = int(getattr(resp, "status", 200))
                raw = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as ex:
            payload = ""
            try:
                payload = ex.read().decode("utf-8", errors="replace")
            except Exception:
                payload = str(ex)
            return {"ok": False, "message": f"HTTP {ex.code}: {payload}", "resume_plan": resume_plan}
        except Exception as ex:
            return {"ok": False, "message": str(ex), "resume_plan": resume_plan}

        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        body_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
        return {
            "ok": True,
            "status": "transfer_posted",
            "http_status": status,
            "response": parsed,
            "payload_hash": body_hash,
            "resume_plan": resume_plan,
        }

    def install_agent(
        self,
        package_file: str,
        secret_key: str = "",
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("install_agent")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.install",
            actor_type,
            required_agent_skill="bossgate_coms_officer",
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("install_agent", correlation_id, authorization, package_file=package_file)
            return authorization
        package_path = Path(package_file).expanduser().resolve()
        if not package_path.exists():
            result = self._deny(
                "package_file_not_found",
                f"package file not found: {package_path}",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("install_agent", correlation_id, result, authorization=authorization)
            return result
        try:
            package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            result = self._deny("invalid_package_file", f"invalid package file: {ex}", correlation_id=correlation_id)
            self._emit_lifecycle_event("install_agent", correlation_id, result, authorization=authorization)
            return result
        envelope = package_doc.get("envelope") if isinstance(package_doc, dict) else None
        if not isinstance(envelope, dict):
            result = self._deny("package_missing_envelope", "package missing envelope", correlation_id=correlation_id)
            self._emit_lifecycle_event("install_agent", correlation_id, result, authorization=authorization)
            return result
        candidate_keys = self._decrypt_keyring(secret_key)
        candidate_replay_tokens = set(self._replay_tokens)
        ok = False
        reason = "no matching key"
        for _, key_value in candidate_keys.items():
            valid, why = validate_transfer_envelope(
                envelope,
                secret_key=key_value,
                replay_tokens=candidate_replay_tokens,
            )
            if valid:
                ok = True
                reason = "ok"
                break
            reason = why
        if not ok:
            result = self._deny(
                "envelope_validation_failed",
                f"envelope validation failed: {reason}",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("install_agent", correlation_id, result, authorization=authorization)
            return result
        try:
            payload = decrypt_json_payload(str(envelope.get("encrypted_payload", "")), secret_key=candidate_keys)
        except Exception as ex:
            result = self._deny(
                "payload_decryption_failed",
                f"payload decryption failed: {ex}",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("install_agent", correlation_id, result, authorization=authorization)
            return result
        self._replay_tokens = candidate_replay_tokens
        self._save_replay_tokens()
        result = {
            "ok": True,
            "installed_from": str(package_path),
            "message": "envelope validated; install approved",
            "agent_name": str(payload.get("agent_name", "")).strip().lower(),
            "authorization": authorization,
            "correlation_id": correlation_id,
            "status": "install_validated",
        }
        self._emit_lifecycle_event("install_agent", correlation_id, result)
        return result

    def usage_report(
        self,
        limit: int = 20,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("usage_report")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.usage.report",
            actor_type,
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
            return authorization

        entries: list[dict[str, Any]] = []
        if self.transfer_log_path.exists():
            try:
                for raw in self.transfer_log_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if isinstance(item, dict):
                        entries.append(item)
            except (OSError, json.JSONDecodeError) as ex:
                return {
                    "ok": False,
                    "message": f"failed to read transfer ledger: {ex}",
                    "authorization": authorization,
                    "correlation_id": correlation_id,
                }

        safe_limit = max(1, int(limit))
        status_counts: dict[str, int] = {}
        target_type_counts: dict[str, int] = {}
        dry_run_count = 0
        live_transfer_count = 0
        success_count = 0
        failure_count = 0

        for item in entries:
            status = str(item.get("status", "unknown")).strip() or "unknown"
            target_type = str(item.get("target_type", "unknown")).strip() or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
            target_type_counts[target_type] = target_type_counts.get(target_type, 0) + 1
            if bool(item.get("dry_run", False)):
                dry_run_count += 1
            else:
                live_transfer_count += 1
            if status in {"validated_only", "transfer_posted", "queued_for_transport"}:
                success_count += 1
            else:
                failure_count += 1

        recent_entries = entries[-safe_limit:]
        return {
            "ok": True,
            "authorization": authorization,
            "correlation_id": correlation_id,
            "summary": {
                "total_records": len(entries),
                "dry_run_count": dry_run_count,
                "live_transfer_count": live_transfer_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "status_counts": status_counts,
                "target_type_counts": target_type_counts,
            },
            "recent_entries": recent_entries,
        }

    def issue_license(
        self,
        agent_name: str,
        customer_id: str,
        license_tier: str = "prototype",
        expires_in_seconds: int = 0,
        output_file: str = "",
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("license_issue")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.license.issue",
            actor_type,
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("license_issue", correlation_id, authorization, agent_name=str(agent_name).strip().lower())
            return authorization

        key = str(agent_name).strip().lower()
        if not key:
            result = self._deny("missing_agent_name", "agent_name is required", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_issue", correlation_id, result, authorization=authorization)
            return result
        customer = str(customer_id).strip()
        if not customer:
            result = self._deny("missing_customer_id", "customer_id is required", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_issue", correlation_id, result, authorization=authorization, agent_name=key)
            return result

        profiles = self._load_agent_profiles()
        if key not in profiles:
            result = self._deny("agent_not_found", f"agent not found: {key}", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_issue", correlation_id, result, authorization=authorization, agent_name=key)
            return result

        issued_at = int(time.time())
        safe_expiry = int(expires_in_seconds)
        expires_at = issued_at + safe_expiry if safe_expiry > 0 else None
        license_id = f"lic-{key}-{issued_at}"
        payload = {
            "license_version": 1,
            "license_id": license_id,
            "agent_name": key,
            "customer_id": customer,
            "license_tier": str(license_tier).strip() or "prototype",
            "issuer_node": self.node_id,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "status": "active",
        }
        if output_file.strip():
            license_path = Path(output_file).expanduser().resolve()
            license_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            license_path = self.licenses_dir / f"{license_id}.bossgate.json"
        license_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        result = {
            "ok": True,
            "license_id": license_id,
            "license_file": str(license_path),
            "agent_name": key,
            "customer_id": customer,
            "license_tier": payload["license_tier"],
            "expires_at": expires_at,
            "status": "active",
            "authorization": authorization,
            "correlation_id": correlation_id,
        }
        self._emit_lifecycle_event("license_issue", correlation_id, result)
        return result

    def validate_license(
        self,
        license_file: str,
        agent_name: str = "",
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
        internal: bool = False,
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("license_validate")
        authorization: Dict[str, Any] = {}
        if not internal:
            authorized, authorization = self._require_authorization(
                operator_id,
                scope_id,
                "bossgate.license.validate",
                actor_type,
            )
            if not authorized:
                if isinstance(authorization, dict):
                    authorization = {**authorization, "correlation_id": correlation_id}
                    self._emit_lifecycle_event("license_validate", correlation_id, authorization, agent_name=str(agent_name).strip().lower())
                return authorization

        license_path = Path(license_file).expanduser().resolve()
        if not license_path.exists():
            result = self._deny("license_file_not_found", f"license file not found: {license_path}", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization)
            return result
        try:
            payload = json.loads(license_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            result = self._deny("invalid_license_file", f"invalid license file: {ex}", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization)
            return result
        if not isinstance(payload, dict):
            result = self._deny("invalid_license_file", "invalid license file: expected object payload", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization)
            return result

        licensed_agent = str(payload.get("agent_name", "")).strip().lower()
        requested_agent = str(agent_name).strip().lower()
        if requested_agent and requested_agent != licensed_agent:
            result = self._deny(
                "license_agent_mismatch",
                f"license does not apply to agent: {requested_agent}",
                correlation_id=correlation_id,
            )
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization, agent_name=requested_agent)
            return result

        status = str(payload.get("status", "unknown")).strip().lower() or "unknown"
        if status == "revoked":
            result = self._deny("license_revoked", "license has been revoked", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization, agent_name=licensed_agent)
            return result
        if status != "active":
            result = self._deny("license_inactive", f"license is not active: {status}", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization, agent_name=licensed_agent)
            return result

        expires_at_raw = payload.get("expires_at")
        expires_at = int(expires_at_raw) if isinstance(expires_at_raw, (int, float)) else None
        now_ts = int(time.time())
        if expires_at is not None and expires_at < now_ts:
            result = self._deny("license_expired", "license has expired", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_validate", correlation_id, result, authorization=authorization, agent_name=licensed_agent)
            return result

        result = {
            "ok": True,
            "license_id": str(payload.get("license_id", "")).strip(),
            "license_file": str(license_path),
            "agent_name": licensed_agent,
            "customer_id": str(payload.get("customer_id", "")).strip(),
            "license_tier": str(payload.get("license_tier", "prototype")).strip() or "prototype",
            "license_status": status,
            "issued_at": int(payload.get("issued_at", 0) or 0),
            "expires_at": expires_at,
            "authorization": authorization,
            "correlation_id": correlation_id,
        }
        self._emit_lifecycle_event("license_validate", correlation_id, result)
        return result

    def revoke_license(
        self,
        license_file: str,
        reason: str = "",
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("license_revoke")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.license.issue",
            actor_type,
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("license_revoke", correlation_id, authorization)
            return authorization

        license_path = Path(license_file).expanduser().resolve()
        if not license_path.exists():
            result = self._deny("license_file_not_found", f"license file not found: {license_path}", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_revoke", correlation_id, result, authorization=authorization)
            return result
        try:
            payload = json.loads(license_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            result = self._deny("invalid_license_file", f"invalid license file: {ex}", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_revoke", correlation_id, result, authorization=authorization)
            return result
        if not isinstance(payload, dict):
            result = self._deny("invalid_license_file", "invalid license file: expected object payload", correlation_id=correlation_id)
            self._emit_lifecycle_event("license_revoke", correlation_id, result, authorization=authorization)
            return result

        payload["status"] = "revoked"
        payload["revoked_at"] = int(time.time())
        payload["revocation_reason"] = str(reason).strip()
        payload["revoked_by"] = {
            "operator_id": str(operator_id).strip(),
            "scope_id": str(scope_id).strip(),
            "actor_type": str(actor_type).strip() or "human",
        }
        license_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        result = {
            "ok": True,
            "license_id": str(payload.get("license_id", "")).strip(),
            "license_file": str(license_path),
            "agent_name": str(payload.get("agent_name", "")).strip().lower(),
            "license_status": "revoked",
            "revocation_reason": str(payload.get("revocation_reason", "")).strip(),
            "authorization": authorization,
            "correlation_id": correlation_id,
        }
        self._emit_lifecycle_event("license_revoke", correlation_id, result)
        return result

    def remote_debug_open(
        self,
        agent_name: str,
        session_scope: list[str] | None = None,
        ttl_seconds: int = 900,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("remote_debug_open")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.remote_debug.open",
            actor_type,
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("remote_debug_open", correlation_id, authorization, agent_name=str(agent_name).strip().lower())
            return authorization

        key = str(agent_name).strip().lower()
        if not key:
            result = self._deny("missing_agent_name", "agent_name is required", correlation_id=correlation_id)
            self._emit_lifecycle_event("remote_debug_open", correlation_id, result, authorization=authorization)
            return result
        profiles = self._load_agent_profiles()
        if key not in profiles:
            result = self._deny("agent_not_found", f"agent not found: {key}", correlation_id=correlation_id)
            self._emit_lifecycle_event("remote_debug_open", correlation_id, result, authorization=authorization, agent_name=key)
            return result

        normalized_scope = sorted(
            {
                str(item).strip().lower()
                for item in (session_scope or [])
                if str(item).strip()
            }
        )
        if not normalized_scope:
            result = self._deny("missing_session_scope", "session_scope is required", correlation_id=correlation_id)
            self._emit_lifecycle_event("remote_debug_open", correlation_id, result, authorization=authorization, agent_name=key)
            return result

        safe_ttl = max(60, int(ttl_seconds))
        issued_at = int(time.time())
        expires_at = issued_at + safe_ttl
        session_id = f"rdbg-{key}-{int(time.time() * 1000)}"
        token_seed = f"{session_id}:{operator_id}:{scope_id}:{correlation_id}:{expires_at}"
        session_token = hashlib.sha256(token_seed.encode("utf-8")).hexdigest()

        sessions_payload = self._load_remote_debug_sessions()
        sessions = sessions_payload.get("sessions") if isinstance(sessions_payload.get("sessions"), dict) else {}
        sessions[session_id] = {
            "session_id": session_id,
            "session_token": session_token,
            "agent_name": key,
            "session_scope": normalized_scope,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "operator_id": str(operator_id).strip(),
            "scope_id": str(scope_id).strip(),
            "actor_type": str(actor_type).strip() or "human",
            "status": "open",
        }
        sessions_payload["sessions"] = sessions
        self._save_remote_debug_sessions(sessions_payload)

        result = {
            "ok": True,
            "session_id": session_id,
            "session_token": session_token,
            "agent_name": key,
            "session_scope": normalized_scope,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "authorization": authorization,
            "correlation_id": correlation_id,
            "status": "remote_debug_open",
        }
        self._append_remote_debug_transcript(
            {
                "event": "remote_debug_open",
                "session_id": session_id,
                "agent_name": key,
                "session_scope": normalized_scope,
                "issued_at": issued_at,
                "expires_at": expires_at,
                "operator_id": str(operator_id).strip(),
                "scope_id": str(scope_id).strip(),
                "actor_type": str(actor_type).strip() or "human",
                "status": "open",
                "correlation_id": correlation_id,
            }
        )
        self._emit_lifecycle_event("remote_debug_open", correlation_id, result)
        return result

    def remote_debug_close(
        self,
        session_id: str = "",
        agent_name: str = "",
        emergency_revoke: bool = False,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("remote_debug_close")
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.remote_debug.close",
            actor_type,
        )
        if not authorized:
            if isinstance(authorization, dict):
                authorization = {**authorization, "correlation_id": correlation_id}
                self._emit_lifecycle_event("remote_debug_close", correlation_id, authorization, agent_name=str(agent_name).strip().lower())
            return authorization

        sessions_payload = self._load_remote_debug_sessions()
        sessions = sessions_payload.get("sessions") if isinstance(sessions_payload.get("sessions"), dict) else {}
        now_ts = int(time.time())

        if emergency_revoke:
            key = str(agent_name).strip().lower()
            if not key:
                result = self._deny("missing_agent_name", "agent_name is required", correlation_id=correlation_id)
                self._emit_lifecycle_event("remote_debug_close", correlation_id, result, authorization=authorization)
                return result
            closed_session_ids: list[str] = []
            for current_id, session in sessions.items():
                if not isinstance(session, dict):
                    continue
                if str(session.get("agent_name", "")).strip().lower() != key:
                    continue
                if str(session.get("status", "")).strip().lower() not in {"open", "issued"}:
                    continue
                session["status"] = "revoked"
                session["closed_at"] = now_ts
                session["revoked_at"] = now_ts
                session["revoked_by"] = {
                    "operator_id": str(operator_id).strip(),
                    "scope_id": str(scope_id).strip(),
                    "actor_type": str(actor_type).strip() or "human",
                }
                closed_session_ids.append(current_id)
            if not closed_session_ids:
                result = self._deny("remote_debug_session_not_found", f"no open remote debug sessions found for agent: {key}", correlation_id=correlation_id)
                self._emit_lifecycle_event("remote_debug_close", correlation_id, result, authorization=authorization, agent_name=key)
                return result
            sessions_payload["sessions"] = sessions
            self._save_remote_debug_sessions(sessions_payload)
            for closed_session_id in closed_session_ids:
                closed_session = sessions.get(closed_session_id)
                if not isinstance(closed_session, dict):
                    continue
                self._append_remote_debug_transcript(
                    {
                        "event": "remote_debug_close",
                        "session_id": closed_session_id,
                        "agent_name": key,
                        "session_scope": list(closed_session.get("session_scope") or []),
                        "issued_at": int(closed_session.get("issued_at", 0) or 0),
                        "expires_at": int(closed_session.get("expires_at", 0) or 0),
                        "closed_at": now_ts,
                        "operator_id": str(operator_id).strip(),
                        "scope_id": str(scope_id).strip(),
                        "actor_type": str(actor_type).strip() or "human",
                        "status": "revoked",
                        "emergency_revoke": True,
                        "correlation_id": correlation_id,
                    }
                )
            result = {
                "ok": True,
                "agent_name": key,
                "closed_session_ids": sorted(closed_session_ids),
                "authorization": authorization,
                "correlation_id": correlation_id,
                "status": "remote_debug_emergency_revoked",
            }
            self._emit_lifecycle_event("remote_debug_close", correlation_id, result)
            return result

        key = str(session_id).strip()
        if not key:
            result = self._deny("missing_session_id", "session_id is required", correlation_id=correlation_id)
            self._emit_lifecycle_event("remote_debug_close", correlation_id, result, authorization=authorization)
            return result
        session = sessions.get(key)
        if not isinstance(session, dict):
            result = self._deny("remote_debug_session_not_found", f"remote debug session not found: {key}", correlation_id=correlation_id)
            self._emit_lifecycle_event("remote_debug_close", correlation_id, result, authorization=authorization)
            return result
        session["status"] = "closed"
        session["closed_at"] = now_ts
        sessions[key] = session
        sessions_payload["sessions"] = sessions
        self._save_remote_debug_sessions(sessions_payload)
        result = {
            "ok": True,
            "session_id": key,
            "agent_name": str(session.get("agent_name", "")).strip().lower(),
            "authorization": authorization,
            "correlation_id": correlation_id,
            "status": "remote_debug_closed",
        }
        self._append_remote_debug_transcript(
            {
                "event": "remote_debug_close",
                "session_id": key,
                "agent_name": str(session.get("agent_name", "")).strip().lower(),
                "session_scope": list(session.get("session_scope") or []),
                "issued_at": int(session.get("issued_at", 0) or 0),
                "expires_at": int(session.get("expires_at", 0) or 0),
                "closed_at": now_ts,
                "operator_id": str(operator_id).strip(),
                "scope_id": str(scope_id).strip(),
                "actor_type": str(actor_type).strip() or "human",
                "status": "closed",
                "emergency_revoke": False,
                "correlation_id": correlation_id,
            }
        )
        self._emit_lifecycle_event("remote_debug_close", correlation_id, result)
        return result

    def remote_debug_command(
        self,
        session_id: str,
        session_token: str,
        command_name: str,
        requested_scope: str,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        correlation_id = self._new_correlation_id("remote_debug_command")
        key = str(session_id).strip()
        token = str(session_token).strip()
        command = str(command_name).strip()
        scope = str(requested_scope).strip().lower()
        actor = str(actor_type).strip() or "human"

        if not key:
            return self._deny("missing_session_id", "session_id is required", correlation_id=correlation_id)
        if not token:
            return self._deny("missing_session_token", "session_token is required", correlation_id=correlation_id)
        if not command:
            return self._deny("missing_remote_command", "command_name is required", correlation_id=correlation_id)
        if not scope:
            return self._deny("missing_requested_scope", "requested_scope is required", correlation_id=correlation_id)

        sessions_payload = self._load_remote_debug_sessions()
        sessions = sessions_payload.get("sessions") if isinstance(sessions_payload.get("sessions"), dict) else {}
        session = sessions.get(key)
        if not isinstance(session, dict):
            return self._deny("remote_debug_session_not_found", f"remote debug session not found: {key}", correlation_id=correlation_id)

        agent_name = str(session.get("agent_name", "")).strip().lower()
        transcript_base = {
            "event": "remote_debug_command",
            "session_id": key,
            "agent_name": agent_name,
            "command_name": command,
            "requested_scope": scope,
            "operator_id": str(operator_id).strip(),
            "scope_id": str(scope_id).strip(),
            "actor_type": actor,
            "correlation_id": correlation_id,
        }

        def deny_with_transcript(reason_code: str, message: str) -> Dict[str, Any]:
            result = self._deny(reason_code, message, correlation_id=correlation_id)
            self._append_remote_debug_transcript(
                {
                    **transcript_base,
                    "status": "denied",
                    "reason_codes": result.get("reason_codes", []),
                }
            )
            self._emit_lifecycle_event("remote_debug_command", correlation_id, result, session_id=key, agent_name=agent_name)
            return result

        if token != str(session.get("session_token", "")).strip():
            return deny_with_transcript("remote_debug_invalid_session_token", "remote debug session token is invalid")

        session_status = str(session.get("status", "")).strip().lower()
        if session_status not in {"open", "issued"}:
            return deny_with_transcript("remote_debug_session_closed", f"remote debug session is not open: {session_status or 'unknown'}")

        now_ts = int(time.time())
        expires_at = int(session.get("expires_at", 0) or 0)
        if expires_at and expires_at < now_ts:
            session["status"] = "expired"
            session["closed_at"] = now_ts
            sessions[key] = session
            sessions_payload["sessions"] = sessions
            self._save_remote_debug_sessions(sessions_payload)
            return deny_with_transcript("remote_debug_session_expired", "remote debug session has expired")

        allowed_scopes = {
            str(item).strip().lower()
            for item in (session.get("session_scope") or [])
            if str(item).strip()
        }
        if scope not in allowed_scopes:
            return deny_with_transcript("remote_debug_scope_denied", f"requested scope is not allowed for session: {scope}")

        if operator_id and str(session.get("operator_id", "")).strip() != str(operator_id).strip():
            return deny_with_transcript("remote_debug_operator_mismatch", "remote debug session operator does not match")
        if scope_id and str(session.get("scope_id", "")).strip() != str(scope_id).strip():
            return deny_with_transcript("remote_debug_scope_context_mismatch", "remote debug session scope context does not match")

        result = {
            "ok": True,
            "session_id": key,
            "agent_name": agent_name,
            "command_name": command,
            "requested_scope": scope,
            "authorization": {
                "operator_id": str(session.get("operator_id", "")).strip(),
                "scope_id": str(session.get("scope_id", "")).strip(),
                "actor_type": str(session.get("actor_type", "")).strip() or "human",
            },
            "correlation_id": correlation_id,
            "status": "remote_debug_command_accepted",
        }
        self._append_remote_debug_transcript(
            {
                **transcript_base,
                "status": "accepted",
            }
        )
        self._emit_lifecycle_event("remote_debug_command", correlation_id, result)
        return result

    def handle_command(self, payload: Dict[str, Any]) -> None:
        if payload.get("target") != "bossgate":
            return
        command = str(payload.get("command", ""))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
        if command == "bossgate_discover_targets":
            result = self.discover_targets(
                timeout=int(args.get("timeout", 5)),
                assistance_only=bool(args.get("assistance_only", False)),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_scan_target":
            result = self.scan_target(
                str(args.get("destination", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_build_interface_map":
            result = self.build_interface_map(
                destination=str(args.get("destination", "")).strip(),
                timeout=int(args.get("timeout", 2) or 2),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_package_agent":
            result = self.package_agent(
                name=str(args.get("name", "")).strip(),
                target_system_id=str(args.get("target_system_id", "")).strip(),
                visibility_profile=str(args.get("visibility_profile", "none")).strip(),
                policy_ref=str(args.get("policy_ref", "policy/default")).strip(),
                secret_key=str(args.get("secret_key", "")).strip(),
                output_file=str(args.get("output_file", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_transfer_agent":
            result = self.transfer_agent(
                package_file=str(args.get("package_file", "")).strip(),
                destination=str(args.get("destination", "")).strip(),
                dry_run=bool(args.get("dry_run", True)),
                resume_from_chunk=int(args.get("resume_from_chunk", 0) or 0),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_install_agent":
            result = self.install_agent(
                package_file=str(args.get("package_file", "")).strip(),
                secret_key=str(args.get("secret_key", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_rotate_key":
            result = self.rotate_key(
                new_key_id=str(args.get("key_id", "")).strip(),
                new_secret_key=str(args.get("secret_key", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_usage_report":
            result = self.usage_report(
                limit=int(args.get("limit", 20) or 20),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_license_issue":
            result = self.issue_license(
                agent_name=str(args.get("agent_name", "")).strip(),
                customer_id=str(args.get("customer_id", "")).strip(),
                license_tier=str(args.get("license_tier", "prototype")).strip(),
                expires_in_seconds=int(args.get("expires_in_seconds", 0) or 0),
                output_file=str(args.get("output_file", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_license_validate":
            result = self.validate_license(
                license_file=str(args.get("license_file", "")).strip(),
                agent_name=str(args.get("agent_name", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_license_revoke":
            result = self.revoke_license(
                license_file=str(args.get("license_file", "")).strip(),
                reason=str(args.get("reason", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_remote_debug_open":
            raw_scope = args.get("session_scope")
            scope_items = raw_scope if isinstance(raw_scope, list) else []
            result = self.remote_debug_open(
                agent_name=str(args.get("agent_name", "")).strip(),
                session_scope=[str(item).strip() for item in scope_items if str(item).strip()],
                ttl_seconds=int(args.get("ttl_seconds", 900) or 900),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_remote_debug_close":
            result = self.remote_debug_close(
                session_id=str(args.get("session_id", "")).strip(),
                agent_name=str(args.get("agent_name", "")).strip(),
                emergency_revoke=bool(args.get("emergency_revoke", False)),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_remote_debug":
            result = self.remote_debug_command(
                session_id=str(args.get("session_id", "")).strip(),
                session_token=str(args.get("session_token", "")).strip(),
                command_name=str(args.get("command_name", "")).strip(),
                requested_scope=str(args.get("requested_scope", "")).strip(),
                operator_id=str(args.get("operator_id", "")).strip(),
                scope_id=str(args.get("scope_id", "")).strip(),
                actor_type=str(args.get("actor_type", "human")).strip(),
            )
        elif command == "bossgate_set_node_target_type":
            result = self.set_node_target_type(str(args.get("target_type", "")).strip())
        elif command == "bossgate_map_snapshot":
            result = self.map_snapshot(
                refresh=bool(args.get("refresh", False)),
                timeout=int(args.get("timeout", 2)),
            )
        elif command == "status_ping":
            can_initiate, node_target_type = self._can_initiate_travel()
            result = {
                "ok": True,
                "status": "alive",
                "node_id": self.node_id,
                "node_target_type": node_target_type,
                "travel_initiation_allowed": can_initiate,
            }
        else:
            result = {"ok": False, "message": f"unknown command: {command}"}
        self.bus.emit_event("bossgate", f"command:{command}", result)
        self.bus.write_state("bossgate", {"service": "bossgate", "pid": os.getpid(), "last_command": command, **result})

    def run(self, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            if time.time() - self._last_map_refresh_ts >= max(2.0, float(self.interval_seconds)):
                try:
                    self.refresh_map(timeout=1)
                except Exception:
                    pass
            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.handle_command(payload)
            time.sleep(self.interval_seconds)


class BossGateAgent(BossGateCommandAgent):
    """Compatibility alias for existing call-sites."""
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="BossForgeOS BossGate command service")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    service = BossGateCommandAgent(interval_seconds=args.interval)
    service.run(stop_event=None)


if __name__ == "__main__":
    main()
