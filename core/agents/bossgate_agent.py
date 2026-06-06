import argparse
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict
from urllib import error, request
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
        self.transfer_log_path = self.bus.state / "bossgate_transfers.jsonl"
        self.keyring_path = self.bus.state / "bossgate_keys.json"
        self.replay_tokens_path = self.bus.state / "bossgate_replay_tokens.json"
        self.node_profile_path = self.bus.state / "bossgate_node_profile.json"
        self.map_path = self.bus.state / "bossgate_map.json"
        self.authorization_registry = BossGateAuthorizationRegistry(self.bus.state / "bossgate_human_roles.json")
        self.node_id = self._load_or_create_node_id()
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self._keyring = self._load_or_create_keyring()
        self._replay_tokens = self._load_replay_tokens()
        self._node_profile = self._load_or_create_node_profile()
        self._last_map_refresh_ts = 0.0

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
        authorized, authorization = self._require_authorization(
            operator_id=operator_id,
            scope_id=scope_id,
            permission="bossgate.key.rotate",
            actor_type=actor_type,
        )
        if not authorized:
            return authorization
        key_id = str(new_key_id).strip() or f"k{int(time.time())}"
        secret = str(new_secret_key).strip() or f"{self.node_id}:{key_id}:{int(time.time())}"
        keys = self._keyring.get("keys") if isinstance(self._keyring.get("keys"), dict) else {}
        keys[key_id] = secret
        self._keyring["keys"] = keys
        self._keyring["active_key_id"] = key_id
        self._save_keyring()
        return {"ok": True, "active_key_id": key_id, "key_count": len(keys), "authorization": authorization}

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
            return False, {
                "ok": False,
                "message": "authorization denied: operator_id and scope_id are required",
                "authorization": authorization,
            }
        if normalized_actor_type == "agent":
            profiles = self._load_agent_profiles()
            profile = profiles.get(authorization["operator_id"].lower())
            if not isinstance(profile, dict):
                return False, {
                    "ok": False,
                    "message": f"authorization denied: unknown agent: {authorization['operator_id']}",
                    "authorization": authorization,
                }
            skills = {str(item).strip().lower() for item in profile.get("skills", []) if str(item).strip()} if isinstance(profile.get("skills"), list) else set()
            if required_agent_skill and required_agent_skill not in skills:
                return False, {
                    "ok": False,
                    "message": f"authorization denied: agent skill is required: {required_agent_skill}",
                    "authorization": authorization,
                }
            return True, authorization
        if normalized_actor_type != "human":
            return False, {
                "ok": False,
                "message": f"authorization denied: unknown actor_type: {normalized_actor_type}",
                "authorization": authorization,
            }
        if not self.authorization_registry.roles_for_user(authorization["operator_id"]):
            return False, {
                "ok": False,
                "message": f"authorization denied: unknown operator: {authorization['operator_id']}",
                "authorization": authorization,
            }
        if permission and not self.authorization_registry.has_permission(authorization["operator_id"], permission):
            return False, {
                "ok": False,
                "message": f"authorization denied: permission is required: {permission}",
                "authorization": authorization,
            }
        return True, authorization

    def discover_targets(
        self,
        timeout: int = 5,
        assistance_only: bool = False,
        operator_id: str = "",
        scope_id: str = "",
        actor_type: str = "human",
    ) -> Dict[str, Any]:
        authorized, authorization = self._require_authorization(operator_id, scope_id, "bossgate.discovery.run", actor_type)
        if not authorized:
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
        authorization: dict[str, Any] = {}
        if not internal:
            authorized, authorization = self._require_authorization(operator_id, scope_id, "bossgate.discovery.run", actor_type)
            if not authorized:
                return authorization
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
        result.setdefault("authorization", authorization)
        return result

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
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.package",
            actor_type,
            required_agent_skill="bossgate_coms_officer",
        )
        if not authorized:
            return authorization
        profiles = self._load_agent_profiles()
        key = name.strip().lower()
        if not key:
            return {"ok": False, "message": "name is required"}
        profile = profiles.get(key)
        if not isinstance(profile, dict):
            return {"ok": False, "message": f"agent not found: {key}"}
        if not bool(profile.get("bossgate_enabled", True)):
            return {"ok": False, "message": f"agent is not bossgate-enabled: {key}"}
        if not str(target_system_id).strip():
            return {"ok": False, "message": "target_system_id is required"}

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
        return {
            "ok": True,
            "agent": key,
            "package_file": str(package_path),
            "target_system_id": str(target_system_id).strip(),
            "visibility_profile": metadata.get("profile", "none"),
            "authorization": authorization,
        }

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
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.transfer",
            actor_type,
            required_agent_skill="bossgate_travel_control",
        )
        if not authorized:
            return authorization
        can_initiate, node_target_type = self._can_initiate_travel()
        if not can_initiate:
            return {
                "ok": False,
                "message": "travel initiation denied: only super gates can initiate travel",
                "node_target_type": node_target_type,
                "allowed_initiators": sorted(SUPER_GATE_TARGET_TYPES),
            }
        package_path = Path(package_file).expanduser().resolve()
        if not package_path.exists():
            return {"ok": False, "message": f"package file not found: {package_path}"}
        package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        package_agent_name = str(package_doc.get("agent_name", "")).strip().lower()
        target_validation = self.scan_target(destination, internal=True)
        if not bool(target_validation.get("allowed_for_transfer", False)):
            return {
                "ok": False,
                "message": "destination is not approved for transfer",
                "destination": destination,
                "target_validation": target_validation,
            }
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
            )
            if not transfer_result.get("ok", False):
                record = {
                    "timestamp": int(time.time()),
                    "node_id": self.node_id,
                    "package_file": str(package_path),
                    "destination": destination,
                    "target_type": str(target_validation.get("target_type", "unknown")),
                    "dry_run": False,
                    "status": "transfer_failed",
                    "error": str(transfer_result.get("message", "")),
                }
                with self.transfer_log_path.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(record, separators=(",", ":")))
                    fp.write("\n")
                return {
                    "ok": False,
                    "destination": destination,
                    "package_file": str(package_path),
                    "dry_run": False,
                    "status": "transfer_failed",
                    "target_validation": target_validation,
                    "message": str(transfer_result.get("message", "")),
                }
            retirement = self._retire_local_agent_traces(package_agent_name, package_path)
        else:
            retirement = {"agent": package_agent_name, "profile_removed": False, "files_deleted": []}

        record = {
            "timestamp": int(time.time()),
            "node_id": self.node_id,
            "package_file": str(package_path),
            "destination": destination,
            "target_type": str(target_validation.get("target_type", "unknown")),
            "dry_run": bool(dry_run),
            "status": str(transfer_result.get("status", "validated_only" if dry_run else "queued_for_transport")),
            "http_status": int(transfer_result.get("http_status", 0) or 0),
            "resume_plan": transfer_result.get("resume_plan", {}),
        }
        with self.transfer_log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, separators=(",", ":")))
            fp.write("\n")
        return {
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
        }

    def _send_transfer_package(self, package_path: Path, destination: str, resume_from_chunk: int = 0) -> dict[str, Any]:
        package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        envelope = package_doc.get("envelope") if isinstance(package_doc, dict) else None
        if not isinstance(envelope, dict):
            return {"ok": False, "message": "package missing envelope"}
        manifest = envelope.get("chunk_manifest")
        chunk_count = int(manifest.get("chunk_count", 0)) if isinstance(manifest, dict) else 0
        safe_resume_from = max(0, int(resume_from_chunk))
        if not isinstance(manifest, dict):
            if safe_resume_from:
                return {"ok": False, "message": "resume requires a package chunk manifest"}
            resume_plan = {}
        else:
            if safe_resume_from > chunk_count:
                return {"ok": False, "message": "resume_from_chunk exceeds package chunk count"}
            resume_plan = build_transfer_resume_plan(envelope, completed_chunk_indexes=list(range(safe_resume_from)))
        correlation_id = f"bg-{self.node_id}-{int(time.time())}"
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
            return {"ok": False, "message": f"HTTP {ex.code}: {payload}"}
        except Exception as ex:
            return {"ok": False, "message": str(ex)}

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
        authorized, authorization = self._require_authorization(
            operator_id,
            scope_id,
            "bossgate.install",
            actor_type,
            required_agent_skill="bossgate_coms_officer",
        )
        if not authorized:
            return authorization
        package_path = Path(package_file).expanduser().resolve()
        if not package_path.exists():
            return {"ok": False, "message": f"package file not found: {package_path}"}
        try:
            package_doc = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            return {"ok": False, "message": f"invalid package file: {ex}"}
        envelope = package_doc.get("envelope") if isinstance(package_doc, dict) else None
        if not isinstance(envelope, dict):
            return {"ok": False, "message": "package missing envelope"}
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
            return {"ok": False, "message": f"envelope validation failed: {reason}"}
        try:
            payload = decrypt_json_payload(str(envelope.get("encrypted_payload", "")), secret_key=candidate_keys)
        except Exception as ex:
            return {"ok": False, "message": f"payload decryption failed: {ex}"}
        self._replay_tokens = candidate_replay_tokens
        self._save_replay_tokens()
        return {
            "ok": True,
            "installed_from": str(package_path),
            "message": "envelope validated; install approved",
            "agent_name": str(payload.get("agent_name", "")).strip().lower(),
            "authorization": authorization,
        }

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
