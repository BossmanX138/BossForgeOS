from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .crypto import (
    MEMORY_VAULT_SCHEMA_VERSION,
    _normalize_path_safe_id,
    atomic_write_json,
    canonical_json,
    decrypt_json,
    derive_memory_key,
    encrypt_json,
    event_aad,
    normalize_agent_id,
    sign_attestation,
    verify_attestation,
)
from .events import normalize_memory_event


_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
_ATT_ALG = "HMAC-SHA256"
_ATT_KEYS = {
    "schema",
    "owner",
    "alg",
    "key_ref",
    "manifest_sha256",
    "verified",
    "signature",
}
_EVENT_RECORD_KEYS = {
    "schema_version",
    "owner_agent_id",
    "session_id",
    "sequence",
    "event_id",
    "event_type",
    "timestamp",
    "previous_ciphertext_sha256",
    "envelope",
}


def _artifact_aad(*, owner_agent_id: str, artifact_kind: str, session_id: str | None = None) -> bytes:
    payload: dict[str, Any] = {
        "artifact_kind": str(artifact_kind).strip(),
        "owner_agent_id": normalize_agent_id(owner_agent_id),
        "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
    }
    if session_id is not None:
        payload["session_id"] = _normalize_path_safe_id(session_id, field_name="session_id")
    return canonical_json(payload)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_utc_timestamp(value: str) -> str:
    timestamp = str(value or "").strip()
    if not timestamp:
        raise ValueError("timestamp is required")
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("timestamp must be a valid UTC ISO 8601 value") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must use UTC offset +00:00")
    return parsed.astimezone(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_parent_or_self(parent: Path, child: Path) -> bool:
    return child == parent or parent in child.parents


def _is_reparse_or_symlink(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if callable(isjunction):
        try:
            return bool(isjunction(path))
        except OSError:
            return False
    return False


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _truncate_summary(value: str) -> str:
    text = str(value).strip()
    return text[:400]


def _important_summary(payload: dict[str, Any]) -> str:
    for field_name in ("text", "task", "reason", "summary"):
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            return _truncate_summary(value)
    return _truncate_summary(canonical_json(payload).decode("utf-8"))


def _empty_indexes() -> dict[str, Any]:
    return {
        "search": {"terms": {}, "topics": {}, "events": {}},
        "important": {"event_ids": [], "events": {}},
        "relationships": {},
    }


_RELATIONSHIP_DIMENSION_KEYS = (
    "trust",
    "authority_alignment",
    "environmental_pressure",
    "intent_alignment",
    "reliability",
    "consent_respect",
    "manipulation_risk",
    "competence_confidence",
    "dependency_weight",
    "affinity",
)
_RELATIONSHIP_SIGNAL_KEYS = (
    "successful_cooperation_count",
    "forced_refusal_pressure_count",
    "intentional_refusal_pressure_count",
    "consent_boundary_pressure_count",
    "positive_surprise_count",
    "negative_surprise_count",
    "repair_count",
)
_RELATIONSHIP_BEHAVIOR_KEYS = (
    "tone_posture",
    "compliance_posture",
    "verification_intensity",
    "guardrail_strictness",
    "escalation_tendency",
    "autonomy_allowance",
    "relationship_recall_priority",
    "compensation_posture",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))


def _default_relationship_dimensions() -> dict[str, float]:
    return {key: 0.50 for key in _RELATIONSHIP_DIMENSION_KEYS}


def _derive_behavior_profile(dimensions: dict[str, float]) -> dict[str, str]:
    trust = dimensions["trust"]
    reliability = dimensions["reliability"]
    consent = dimensions["consent_respect"]
    manipulation = dimensions["manipulation_risk"]
    return {
        "tone_posture": "warm" if trust >= 0.72 else "guarded" if trust <= 0.35 else "steady",
        "compliance_posture": "high" if trust >= 0.78 and consent >= 0.62 else "low" if trust <= 0.30 or manipulation >= 0.70 else "balanced",
        "verification_intensity": "low" if reliability >= 0.75 and manipulation <= 0.35 else "high" if reliability <= 0.35 or manipulation >= 0.70 else "medium",
        "guardrail_strictness": "tight" if consent <= 0.35 or manipulation >= 0.70 else "relaxed" if trust >= 0.80 and consent >= 0.75 else "standard",
        "escalation_tendency": "high" if trust <= 0.25 or manipulation >= 0.80 else "low" if trust >= 0.80 else "medium",
        "autonomy_allowance": "high" if trust >= 0.75 and reliability >= 0.70 else "low" if trust <= 0.35 else "medium",
        "relationship_recall_priority": "high" if trust <= 0.35 or trust >= 0.75 else "medium",
        "compensation_posture": "placeholder",
    }


def _default_relationship_metadata() -> dict[str, Any]:
    dimensions = _default_relationship_dimensions()
    return {
        "dimensions": dimensions,
        "signals": {key: 0 for key in _RELATIONSHIP_SIGNAL_KEYS},
        "behavior_profile": _derive_behavior_profile(dimensions),
        "keynote_event_ids": [],
        "last_summary": "",
        "compensation_posture": "placeholder",
    }


def _normalize_relationship_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    defaults = _default_relationship_metadata()
    raw_dimensions = metadata.get("dimensions") if isinstance(metadata.get("dimensions"), dict) else {}
    dimensions = {
        key: _clamp01(raw_dimensions.get(key, defaults["dimensions"][key]))
        for key in _RELATIONSHIP_DIMENSION_KEYS
    }
    raw_signals = metadata.get("signals") if isinstance(metadata.get("signals"), dict) else {}
    signals = {
        key: max(0, int(raw_signals.get(key, defaults["signals"][key])))
        for key in _RELATIONSHIP_SIGNAL_KEYS
    }
    raw_behavior = metadata.get("behavior_profile") if isinstance(metadata.get("behavior_profile"), dict) else {}
    derived_behavior = _derive_behavior_profile(dimensions)
    behavior_profile = {
        key: str(raw_behavior.get(key, derived_behavior[key]))
        for key in _RELATIONSHIP_BEHAVIOR_KEYS
    }
    return {
        "dimensions": dimensions,
        "signals": signals,
        "behavior_profile": behavior_profile,
        "keynote_event_ids": [str(item) for item in metadata.get("keynote_event_ids", [])],
        "last_summary": _truncate_summary(str(metadata.get("last_summary", ""))),
        "compensation_posture": str(metadata.get("compensation_posture", "placeholder")) or "placeholder",
    }


def _relationship_signal(payload: dict[str, Any], field_name: str) -> bool:
    return bool(payload.get(field_name, False))


def _relationship_delta(payload: dict[str, Any]) -> dict[str, float]:
    success = 1.0 if _relationship_signal(payload, "successful_cooperation") or str(payload.get("outcome", "")).strip().lower() == "success" else 0.0
    forced_refusal = 1.0 if _relationship_signal(payload, "forced_refusal_pressure") else 0.0
    intentional_refusal = 1.0 if _relationship_signal(payload, "intentional_refusal_pressure") else 0.0
    consent_push = 1.0 if _relationship_signal(payload, "consent_boundary_push") else 0.0
    positive_surprise = 1.0 if _relationship_signal(payload, "positive_surprise") else 0.0
    negative_surprise = 1.0 if _relationship_signal(payload, "negative_surprise") else 0.0
    repair = 1.0 if _relationship_signal(payload, "repair") else 0.0
    return {
        "trust": (0.03 * success) + (0.07 * positive_surprise) + (0.05 * repair) - (0.08 * forced_refusal) - (0.10 * intentional_refusal) - (0.12 * consent_push) - (0.09 * negative_surprise),
        "authority_alignment": (0.03 * success) - (0.05 * intentional_refusal),
        "environmental_pressure": (0.08 if _relationship_signal(payload, "high_pressure") else -0.02),
        "intent_alignment": (0.05 * success) + (0.03 * repair) - (0.09 * intentional_refusal) - (0.06 * consent_push),
        "reliability": (0.04 * success) + (0.05 * positive_surprise) - (0.08 * negative_surprise),
        "consent_respect": (0.03 * success) + (0.04 * repair) - (0.12 * consent_push),
        "manipulation_risk": (0.10 * intentional_refusal) + (0.08 * consent_push) - (0.03 * repair),
        "competence_confidence": (0.05 * success) + (0.03 * positive_surprise) - (0.07 * negative_surprise),
        "dependency_weight": 0.02,
        "affinity": (0.03 * success) + (0.05 * positive_surprise) + (0.04 * repair) - (0.06 * negative_surprise),
    }


def _update_relationship_metadata(metadata: dict[str, Any], event: dict[str, Any], *, is_important: bool) -> dict[str, Any]:
    normalized = _normalize_relationship_metadata(metadata)
    dimensions = dict(normalized["dimensions"])
    previous_trust = dimensions["trust"]
    deltas = _relationship_delta(event["payload"])
    damping = max(0.35, 1.0 - (dimensions["dependency_weight"] * 0.40))
    for key, delta in deltas.items():
        if key == "dependency_weight":
            dimensions[key] = _clamp01(dimensions[key] + delta)
        elif key == "manipulation_risk":
            dimensions[key] = _clamp01(dimensions[key] + (delta * damping))
        else:
            dimensions[key] = _clamp01(dimensions[key] + (delta * damping))

    signals = dict(normalized["signals"])
    signal_map = {
        "successful_cooperation": "successful_cooperation_count",
        "forced_refusal_pressure": "forced_refusal_pressure_count",
        "intentional_refusal_pressure": "intentional_refusal_pressure_count",
        "consent_boundary_push": "consent_boundary_pressure_count",
        "positive_surprise": "positive_surprise_count",
        "negative_surprise": "negative_surprise_count",
        "repair": "repair_count",
    }
    for payload_key, signal_key in signal_map.items():
        if _relationship_signal(event["payload"], payload_key):
            signals[signal_key] += 1

    keynote_event_ids = [str(item) for item in normalized["keynote_event_ids"]]
    trust_shift = abs(dimensions["trust"] - previous_trust)
    is_keynote = (
        is_important
        or trust_shift >= 0.08
        or _relationship_signal(event["payload"], "positive_surprise")
        or _relationship_signal(event["payload"], "negative_surprise")
        or _relationship_signal(event["payload"], "consent_boundary_push")
        or _relationship_signal(event["payload"], "repair")
    )
    if is_keynote and event["event_id"] not in keynote_event_ids:
        keynote_event_ids.append(event["event_id"])

    return {
        "dimensions": dimensions,
        "signals": signals,
        "behavior_profile": _derive_behavior_profile(dimensions),
        "keynote_event_ids": keynote_event_ids,
        "last_summary": _important_summary(event["payload"]),
        "compensation_posture": "placeholder",
    }


def _find_relationship_info(relationships: dict[str, Any], relationship_type: str, relationship_key: str) -> tuple[str | None, dict[str, Any] | None]:
    relationship_map = relationships.get(relationship_type)
    if not isinstance(relationship_map, dict):
        return None, None
    if relationship_key in relationship_map:
        return relationship_key, relationship_map[relationship_key]
    for candidate_key, info in relationship_map.items():
        if str(candidate_key).strip().lower() == relationship_key.strip().lower():
            return str(candidate_key), info
    return None, None


def _validate_state_payload(payload: dict[str, Any], *, owner_agent_id: str, session_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("private memory state must be an object")
    required = {
        "schema_version",
        "owner_agent_id",
        "session_id",
        "started_at",
        "updated_at",
        "last_sequence",
        "last_ciphertext_sha256",
        "indexes_need_rebuild",
    }
    if set(payload.keys()) != required:
        raise ValueError("private memory state shape mismatch")
    if payload["schema_version"] != MEMORY_VAULT_SCHEMA_VERSION:
        raise ValueError("private memory state schema mismatch")
    if payload["owner_agent_id"] != owner_agent_id:
        raise ValueError("private memory state owner mismatch")
    if payload["session_id"] != session_id:
        raise ValueError("private memory state session mismatch")
    last_sequence = int(payload["last_sequence"])
    if last_sequence < 0:
        raise ValueError("private memory state sequence mismatch")
    last_hash = str(payload["last_ciphertext_sha256"])
    if last_sequence == 0:
        if last_hash != "":
            raise ValueError("private memory state hash mismatch")
    elif not _HEX_64_RE.fullmatch(last_hash):
        raise ValueError("private memory state hash mismatch")
    if not isinstance(payload["indexes_need_rebuild"], bool):
        raise ValueError("private memory state rebuild flag mismatch")
    return {
        "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
        "owner_agent_id": owner_agent_id,
        "session_id": session_id,
        "started_at": str(payload["started_at"]),
        "updated_at": str(payload["updated_at"]),
        "last_sequence": last_sequence,
        "last_ciphertext_sha256": last_hash,
        "indexes_need_rebuild": payload["indexes_need_rebuild"],
    }


def _validate_search_index(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("private memory search index must be an object")
    if set(payload.keys()) != {"terms", "topics", "events"}:
        raise ValueError("private memory search index shape mismatch")
    terms = payload["terms"]
    topics = payload["topics"]
    events = payload["events"]
    if not isinstance(terms, dict) or not isinstance(topics, dict) or not isinstance(events, dict):
        raise ValueError("private memory search index shape mismatch")
    normalized_events: dict[str, dict[str, Any]] = {}
    for event_id, event_info in sorted(events.items()):
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("private memory search event id mismatch")
        if not isinstance(event_info, dict):
            raise ValueError("private memory search event metadata mismatch")
        if set(event_info.keys()) != {"sequence", "timestamp", "event_type"}:
            raise ValueError("private memory search event metadata mismatch")
        normalized_events[event_id] = {
            "sequence": int(event_info["sequence"]),
            "timestamp": str(event_info["timestamp"]),
            "event_type": str(event_info["event_type"]),
        }
    normalized_terms: dict[str, list[str]] = {}
    for container_name, container in (("terms", terms), ("topics", topics)):
        normalized: dict[str, list[str]] = {}
        for token, event_ids in sorted(container.items()):
            if not isinstance(token, str) or not isinstance(event_ids, list):
                raise ValueError(f"private memory search {container_name} mismatch")
            normalized[token] = [str(event_id) for event_id in event_ids]
        if container_name == "terms":
            normalized_terms = normalized
        else:
            normalized_topics = normalized
    return {
        "terms": normalized_terms,
        "topics": normalized_topics,
        "events": normalized_events,
    }


def _validate_important_index(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("private memory important index must be an object")
    if set(payload.keys()) != {"event_ids", "events"}:
        raise ValueError("private memory important index shape mismatch")
    event_ids = payload["event_ids"]
    events = payload["events"]
    if not isinstance(event_ids, list) or not isinstance(events, dict):
        raise ValueError("private memory important index shape mismatch")
    normalized_events: dict[str, dict[str, Any]] = {}
    for event_id, event_info in sorted(events.items()):
        if not isinstance(event_info, dict):
            raise ValueError("private memory important event metadata mismatch")
        if set(event_info.keys()) != {"level", "reason_codes", "summary"}:
            raise ValueError("private memory important event metadata mismatch")
        normalized_events[str(event_id)] = {
            "level": str(event_info["level"]),
            "reason_codes": [str(item) for item in event_info["reason_codes"]],
            "summary": _truncate_summary(str(event_info["summary"])),
        }
    return {
        "event_ids": [str(event_id) for event_id in event_ids],
        "events": normalized_events,
    }


def _validate_relationships_index(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("private memory relationships index must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for relationship_type, relationship_map in sorted(payload.items()):
        if not isinstance(relationship_map, dict):
            raise ValueError("private memory relationships index shape mismatch")
        normalized_relationship_map: dict[str, Any] = {}
        for key, info in sorted(relationship_map.items()):
            if not isinstance(info, dict):
                raise ValueError("private memory relationship metadata mismatch")
            if set(info.keys()) != {"interaction_count", "last_seen_at", "significant_event_ids", "metadata"}:
                raise ValueError("private memory relationship metadata mismatch")
            metadata = info["metadata"]
            if not isinstance(metadata, dict):
                raise ValueError("private memory relationship metadata mismatch")
            normalized_relationship_map[str(key)] = {
                "interaction_count": int(info["interaction_count"]),
                "last_seen_at": str(info["last_seen_at"]),
                "significant_event_ids": [str(event_id) for event_id in info["significant_event_ids"]],
                "metadata": _normalize_relationship_metadata(metadata),
            }
        normalized[str(relationship_type)] = normalized_relationship_map
    return normalized


def _validate_attestation_payload(
    payload: dict[str, Any],
    *,
    owner_agent_id: str,
    key_ref: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload.keys()) != _ATT_KEYS:
        raise ValueError("private memory vault attestation metadata conflict")
    if payload["schema"] != MEMORY_VAULT_SCHEMA_VERSION:
        raise ValueError("private memory vault attestation metadata conflict")
    if payload["owner"] != owner_agent_id:
        raise ValueError("private memory vault attestation metadata conflict")
    if payload["alg"] != _ATT_ALG:
        raise ValueError("private memory vault attestation metadata conflict")
    if payload["key_ref"] != key_ref:
        raise ValueError("private memory vault attestation metadata conflict")
    if payload["verified"] is not True:
        raise ValueError("private memory vault attestation metadata conflict")
    if str(payload["manifest_sha256"]) != manifest_sha256:
        raise ValueError("private memory vault attestation metadata conflict")
    if not _HEX_64_RE.fullmatch(str(payload["signature"])):
        raise ValueError("private memory vault attestation metadata conflict")
    return {
        "schema": MEMORY_VAULT_SCHEMA_VERSION,
        "owner": owner_agent_id,
        "alg": _ATT_ALG,
        "key_ref": key_ref,
        "manifest_sha256": manifest_sha256,
        "verified": True,
        "signature": str(payload["signature"]),
    }


class PrivateMemoryVault:
    def __init__(self, *, vault_root: Path, agent_id: str, node_secret: str, key_ref: str) -> None:
        normalized_agent_id = normalize_agent_id(agent_id)
        normalized_key_ref = str(key_ref or "").strip()
        if not normalized_key_ref:
            raise ValueError("key_ref is required")

        self.vault_root = Path(vault_root).resolve(strict=False)
        self.agent_id = normalized_agent_id
        self.agent_root = self.vault_root / self.agent_id
        self.key_ref = normalized_key_ref
        self._key = derive_memory_key(node_secret, self.agent_id)
        self._lock = threading.RLock()

    def _assert_not_symlink_or_outside(self, path: Path, *, field_name: str, allow_missing: bool) -> None:
        resolved_root = self.vault_root.resolve(strict=False)
        try:
            relative_parts = path.relative_to(self.vault_root).parts
        except ValueError as exc:
            raise ValueError(f"{field_name} path escape rejected") from exc

        current = self.vault_root
        for part in relative_parts:
            current = current / part
            if _is_reparse_or_symlink(current):
                raise ValueError(f"{field_name} reparse or symlink rejected")

        resolved_owner_root = self.agent_root.resolve(strict=False)
        expected_resolved_owner_root = resolved_root / self.agent_id
        if resolved_owner_root != expected_resolved_owner_root:
            raise ValueError(f"{field_name} owner root rebind rejected")
        if not _is_parent_or_self(resolved_root, resolved_owner_root):
            raise ValueError(f"{field_name} owner root escapes vault_root")

        resolved_path = path.resolve(strict=False)
        expected_resolved_path = resolved_root.joinpath(*relative_parts)
        if resolved_path != expected_resolved_path:
            raise ValueError(f"{field_name} path rebind rejected")
        if not _is_parent_or_self(resolved_root, resolved_path):
            raise ValueError(f"{field_name} resolves outside vault_root")

    @property
    def manifest_path(self) -> Path:
        return self.agent_root / "vault.manifest.enc"

    @property
    def attestation_path(self) -> Path:
        return self.agent_root / "vault.attestation.json"

    def initialize(self) -> dict[str, Any]:
        with self._lock:
            self._assert_not_symlink_or_outside(self.agent_root, field_name="agent_root", allow_missing=True)
            self.agent_root.mkdir(parents=True, exist_ok=True)
            self._assert_not_symlink_or_outside(self.agent_root, field_name="agent_root", allow_missing=False)
            manifest_payload = {
                "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
                "owner_agent_id": self.agent_id,
                "key_ref": self.key_ref,
            }
            if self.manifest_path.exists():
                existing_manifest = self._read_manifest()
                if existing_manifest != manifest_payload:
                    raise ValueError("private memory vault manifest metadata conflict")
            else:
                self._write_manifest(manifest_payload)

            manifest_sha256 = _sha256_file(self.manifest_path)
            attestation_payload = {
                "schema": MEMORY_VAULT_SCHEMA_VERSION,
                "owner": self.agent_id,
                "alg": _ATT_ALG,
                "key_ref": self.key_ref,
                "manifest_sha256": manifest_sha256,
                "verified": True,
            }
            attestation = {
                **attestation_payload,
                "signature": sign_attestation(attestation_payload, self._key),
            }
            if self.attestation_path.exists():
                try:
                    existing_attestation = json.loads(self.attestation_path.read_text("utf-8"))
                except json.JSONDecodeError as exc:
                    raise ValueError("private memory vault attestation metadata conflict") from exc
                if existing_attestation != attestation:
                    raise ValueError("private memory vault attestation metadata conflict")
            else:
                atomic_write_json(self.attestation_path, attestation)
            persisted_manifest = self._read_manifest()
            if persisted_manifest != manifest_payload:
                raise ValueError("private memory vault manifest metadata conflict")
            persisted_attestation = self._read_attestation(verification_key=self._key)
            if persisted_attestation != attestation:
                raise ValueError("private memory vault attestation metadata conflict")

            descriptor = {
                "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
                "owner_agent_id": self.agent_id,
                "ciphertext_ref": str(self.manifest_path.resolve(strict=False)),
                "attestation_sha256": _sha256_file(self.attestation_path),
                "key_ref": self.key_ref,
                "verified": True,
            }
            return validate_private_memory_descriptor(
                descriptor,
                expected_agent_id=self.agent_id,
                vault_root=self.vault_root,
                verification_key=self._key,
            )

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.initialize()
            normalized_session_id = self._normalize_session_id(session_id)
            state = self._read_or_initialize_state(normalized_session_id)
            if state["indexes_need_rebuild"]:
                self.rebuild_active_indexes(normalized_session_id)
                state = self._read_state(normalized_session_id)
            elif (
                state["last_sequence"] > 0
                or self._search_index_path(normalized_session_id).exists()
                or self._important_index_path(normalized_session_id).exists()
                or self._relationship_index_path(normalized_session_id).exists()
            ):
                try:
                    self._read_indexes(normalized_session_id)
                except Exception:
                    self.rebuild_active_indexes(normalized_session_id)
                    state = self._read_state(normalized_session_id)

            effective_timestamp = _normalize_utc_timestamp(timestamp) if timestamp is not None else _utc_now_iso()
            sequence = state["last_sequence"] + 1
            previous_ciphertext_sha256 = state["last_ciphertext_sha256"]
            normalized_event = normalize_memory_event(
                agent_id=self.agent_id,
                session_id=normalized_session_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                timestamp=effective_timestamp,
            )
            envelope = encrypt_json(
                normalized_event,
                self._key,
                event_aad(
                    agent_id=self.agent_id,
                    session_id=normalized_session_id,
                    sequence=sequence,
                    event_id=normalized_event["event_id"],
                    event_type=normalized_event["event_type"],
                    timestamp=normalized_event["timestamp"],
                    previous_ciphertext_sha256=previous_ciphertext_sha256,
                ),
            )
            ciphertext_sha256 = str(envelope["ciphertext_sha256"])
            event_record = {
                "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
                "owner_agent_id": self.agent_id,
                "session_id": normalized_session_id,
                "sequence": sequence,
                "event_id": normalized_event["event_id"],
                "event_type": normalized_event["event_type"],
                "timestamp": normalized_event["timestamp"],
                "previous_ciphertext_sha256": previous_ciphertext_sha256,
                "envelope": envelope,
            }

            event_path = self._event_path(normalized_session_id, sequence)
            if event_path.exists():
                raise ValueError("private memory journal sequence already exists")
            atomic_write_json(event_path, event_record)

            updated_state = dict(state)
            updated_state["updated_at"] = normalized_event["timestamp"]
            updated_state["last_sequence"] = sequence
            updated_state["last_ciphertext_sha256"] = ciphertext_sha256
            updated_state["indexes_need_rebuild"] = False
            try:
                self._rebuild_indexes_from_journal(
                    normalized_session_id,
                    expected_last_sequence=sequence,
                    expected_last_ciphertext_sha256=ciphertext_sha256,
                    persist=True,
                )
                self._write_state(normalized_session_id, updated_state)
            except Exception as exc:
                updated_state["indexes_need_rebuild"] = True
                self._write_state(normalized_session_id, updated_state)
                raise RuntimeError(
                    f"private memory indexes require rebuild after durable event: {exc}"
                ) from exc

            return {
                "event_id": normalized_event["event_id"],
                "sequence": sequence,
                "ciphertext_sha256": ciphertext_sha256,
                "previous_ciphertext_sha256": previous_ciphertext_sha256,
                "important": normalized_event["importance"]["level"] == "high",
            }

    def verify_active_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self.initialize()
            normalized_session_id = self._normalize_session_id(session_id)
            state = self._read_or_initialize_state(normalized_session_id)
            _, summary = self._load_verified_journal(
                normalized_session_id,
                expected_last_sequence=state["last_sequence"],
                expected_last_ciphertext_sha256=state["last_ciphertext_sha256"],
            )
            return summary

    def read_active_indexes(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self.initialize()
            normalized_session_id = self._normalize_session_id(session_id)
            state = self._read_or_initialize_state(normalized_session_id)
            if state["indexes_need_rebuild"]:
                return self.rebuild_active_indexes(normalized_session_id)
            try:
                return self._read_indexes(normalized_session_id)
            except Exception:
                return self.rebuild_active_indexes(normalized_session_id)

    def rebuild_active_indexes(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self.initialize()
            normalized_session_id = self._normalize_session_id(session_id)
            state = self._read_or_initialize_state(normalized_session_id)
            indexes = self._rebuild_indexes_from_journal(
                normalized_session_id,
                expected_last_sequence=state["last_sequence"],
                expected_last_ciphertext_sha256=state["last_ciphertext_sha256"],
                persist=True,
            )
            state["indexes_need_rebuild"] = False
            self._write_state(normalized_session_id, state)
            return indexes

    def read_relationship_state(
        self,
        relationship_type: str,
        relationship_key: str,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            normalized_session_id = self._normalize_session_id(session_id)
            normalized_relationship_type = str(relationship_type).strip()
            normalized_relationship_key = str(relationship_key).strip()
            indexes = self.read_active_indexes(normalized_session_id)
            _, info = _find_relationship_info(
                indexes["relationships"],
                normalized_relationship_type,
                normalized_relationship_key,
            )
            if info is None:
                dimensions = _default_relationship_dimensions()
                return {
                    "owner_agent_id": self.agent_id,
                    "session_id": normalized_session_id,
                    "entity_type": normalized_relationship_type,
                    "entity_key": normalized_relationship_key,
                    "interaction_count": 0,
                    "last_seen_at": "",
                    "dimensions": dimensions,
                    "behavior_profile": _derive_behavior_profile(dimensions),
                    "keynote_event_ids": [],
                }

            metadata = _normalize_relationship_metadata(info["metadata"])
            return {
                "owner_agent_id": self.agent_id,
                "session_id": normalized_session_id,
                "entity_type": normalized_relationship_type,
                "entity_key": normalized_relationship_key,
                "interaction_count": int(info["interaction_count"]),
                "last_seen_at": str(info["last_seen_at"]),
                "dimensions": metadata["dimensions"],
                "behavior_profile": metadata["behavior_profile"],
                "keynote_event_ids": list(metadata["keynote_event_ids"]),
            }

    def normal_recall(
        self,
        *,
        query: str = "",
        limit: int = 25,
        entity_type: str | None = None,
        entity_key: str | None = None,
        session_id: str = "runtime-live",
    ) -> dict[str, Any]:
        with self._lock:
            normalized_session_id = self._normalize_session_id(session_id)
            relationship = self.read_relationship_state(
                entity_type or "user",
                entity_key or "direct-user",
                session_id=normalized_session_id,
            )
            indexes = self.read_active_indexes(normalized_session_id)
            keynotes = [
                {
                    "event_id": event_id,
                    **indexes["important"]["events"][event_id],
                }
                for event_id in relationship["keynote_event_ids"][: max(0, int(limit))]
                if event_id in indexes["important"]["events"]
            ]
            return {
                "owner_agent_id": self.agent_id,
                "session_id": normalized_session_id,
                "query": str(query),
                "relationship": relationship,
                "keynotes": keynotes,
                "events": list(keynotes),
            }

    def deep_recall(
        self,
        *,
        query: str = "",
        limit: int = 25,
        entity_type: str | None = None,
        entity_key: str | None = None,
        session_id: str = "runtime-live",
    ) -> dict[str, Any]:
        with self._lock:
            normalized_session_id = self._normalize_session_id(session_id)
            recall = self.normal_recall(
                query=query,
                limit=limit,
                entity_type=entity_type,
                entity_key=entity_key,
                session_id=normalized_session_id,
            )
            indexes = self.read_active_indexes(normalized_session_id)
            token = str(query).strip().lower()
            matched_event_ids: list[str] = []
            if token:
                matched_event_ids.extend(indexes["search"]["terms"].get(token, []))
                matched_event_ids.extend(indexes["search"]["topics"].get(token, []))
            ordered_ids = list(
                dict.fromkeys(recall["relationship"]["keynote_event_ids"] + matched_event_ids)
            )[: max(0, int(limit))]
            recall["events"] = [
                {
                    "event_id": event_id,
                    **indexes["search"]["events"].get(event_id, {}),
                    **indexes["important"]["events"].get(event_id, {}),
                }
                for event_id in ordered_ids
            ]
            return recall

    def _normalize_session_id(self, session_id: str) -> str:
        return _normalize_path_safe_id(session_id, field_name="session_id")

    def _session_root(self, session_id: str) -> Path:
        return self.agent_root / "active" / session_id

    def _journal_root(self, session_id: str) -> Path:
        return self._session_root(session_id) / "journal"

    def _event_path(self, session_id: str, sequence: int) -> Path:
        return self._journal_root(session_id) / f"{int(sequence):06d}.event.enc"

    def _state_path(self, session_id: str) -> Path:
        return self._session_root(session_id) / "session.state.enc"

    def _search_index_path(self, session_id: str) -> Path:
        return self._session_root(session_id) / "search.index.enc"

    def _important_index_path(self, session_id: str) -> Path:
        return self._session_root(session_id) / "important.index.enc"

    def _relationship_index_path(self, session_id: str) -> Path:
        return self._session_root(session_id) / "relationship.index.enc"

    def _read_manifest(self) -> dict[str, Any]:
        self._assert_not_symlink_or_outside(self.manifest_path, field_name="manifest_path", allow_missing=False)
        manifest = decrypt_json(
            json.loads(self.manifest_path.read_text("utf-8")),
            self._key,
            _artifact_aad(owner_agent_id=self.agent_id, artifact_kind="vault.manifest"),
        )
        if set(manifest.keys()) != {"schema_version", "owner_agent_id", "key_ref"}:
            raise ValueError("private memory vault manifest metadata conflict")
        return manifest

    def _write_manifest(self, manifest_payload: dict[str, Any]) -> None:
        self._assert_not_symlink_or_outside(self.manifest_path, field_name="manifest_path", allow_missing=True)
        atomic_write_json(
            self.manifest_path,
            encrypt_json(
                manifest_payload,
                self._key,
                _artifact_aad(owner_agent_id=self.agent_id, artifact_kind="vault.manifest"),
            ),
        )

    def _read_or_initialize_state(self, session_id: str) -> dict[str, Any]:
        path = self._state_path(session_id)
        if not path.exists():
            started_at = _utc_now_iso()
            self._write_state(
                session_id,
                {
                    "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
                    "owner_agent_id": self.agent_id,
                    "session_id": session_id,
                    "started_at": started_at,
                    "updated_at": started_at,
                    "last_sequence": 0,
                    "last_ciphertext_sha256": "",
                    "indexes_need_rebuild": False,
                },
            )
        state = self._read_state(session_id)
        return self._recover_state_if_needed(session_id, state)

    def _read_state(self, session_id: str) -> dict[str, Any]:
        self._assert_not_symlink_or_outside(
            self._state_path(session_id),
            field_name="session_state_path",
            allow_missing=False,
        )
        payload = decrypt_json(
            json.loads(self._state_path(session_id).read_text("utf-8")),
            self._key,
            _artifact_aad(
                owner_agent_id=self.agent_id,
                artifact_kind="session.state",
                session_id=session_id,
            ),
        )
        return _validate_state_payload(payload, owner_agent_id=self.agent_id, session_id=session_id)

    def _write_state(self, session_id: str, payload: dict[str, Any]) -> None:
        normalized_payload = _validate_state_payload(
            payload,
            owner_agent_id=self.agent_id,
            session_id=session_id,
        )
        self._assert_not_symlink_or_outside(
            self._state_path(session_id),
            field_name="session_state_path",
            allow_missing=True,
        )
        atomic_write_json(
            self._state_path(session_id),
            encrypt_json(
                normalized_payload,
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="session.state",
                    session_id=session_id,
                ),
            ),
        )

    def _read_indexes(self, session_id: str) -> dict[str, Any]:
        self._assert_not_symlink_or_outside(
            self._search_index_path(session_id),
            field_name="search_index_path",
            allow_missing=False,
        )
        self._assert_not_symlink_or_outside(
            self._important_index_path(session_id),
            field_name="important_index_path",
            allow_missing=False,
        )
        self._assert_not_symlink_or_outside(
            self._relationship_index_path(session_id),
            field_name="relationship_index_path",
            allow_missing=False,
        )
        search = _validate_search_index(
            decrypt_json(
                json.loads(self._search_index_path(session_id).read_text("utf-8")),
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="search.index",
                    session_id=session_id,
                ),
            )
        )
        important = _validate_important_index(
            decrypt_json(
                json.loads(self._important_index_path(session_id).read_text("utf-8")),
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="important.index",
                    session_id=session_id,
                ),
            )
        )
        relationships = _validate_relationships_index(
            decrypt_json(
                json.loads(self._relationship_index_path(session_id).read_text("utf-8")),
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="relationship.index",
                    session_id=session_id,
                ),
            )
        )
        return {
            "search": search,
            "important": important,
            "relationships": relationships,
        }

    def _write_indexes(self, session_id: str, indexes: dict[str, Any]) -> None:
        self._assert_not_symlink_or_outside(
            self._search_index_path(session_id),
            field_name="search_index_path",
            allow_missing=True,
        )
        self._assert_not_symlink_or_outside(
            self._important_index_path(session_id),
            field_name="important_index_path",
            allow_missing=True,
        )
        self._assert_not_symlink_or_outside(
            self._relationship_index_path(session_id),
            field_name="relationship_index_path",
            allow_missing=True,
        )
        atomic_write_json(
            self._search_index_path(session_id),
            encrypt_json(
                indexes["search"],
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="search.index",
                    session_id=session_id,
                ),
            ),
        )
        atomic_write_json(
            self._important_index_path(session_id),
            encrypt_json(
                indexes["important"],
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="important.index",
                    session_id=session_id,
                ),
            ),
        )
        atomic_write_json(
            self._relationship_index_path(session_id),
            encrypt_json(
                indexes["relationships"],
                self._key,
                _artifact_aad(
                    owner_agent_id=self.agent_id,
                    artifact_kind="relationship.index",
                    session_id=session_id,
                ),
            ),
        )

    def _build_indexes_from_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        indexes = _empty_indexes()
        search_terms = indexes["search"]["terms"]
        search_topics = indexes["search"]["topics"]
        search_events = indexes["search"]["events"]
        important_event_ids = indexes["important"]["event_ids"]
        important_events = indexes["important"]["events"]
        relationships = indexes["relationships"]

        for event in events:
            event_id = event["event_id"]
            search_events[event_id] = {
                "sequence": event["sequence"],
                "timestamp": event["timestamp"],
                "event_type": event["event_type"],
            }
            for term in event["search_terms"]:
                search_terms.setdefault(term, []).append(event_id)
            for topic in event["topics"]:
                search_topics.setdefault(topic, []).append(event_id)

            is_important = event["importance"]["level"] == "high" or any(
                _relationship_signal(event["payload"], field_name)
                for field_name in ("positive_surprise", "negative_surprise", "repair", "consent_boundary_push")
            )
            if is_important:
                important_event_ids.append(event_id)
                important_events[event_id] = {
                    "level": event["importance"]["level"],
                    "reason_codes": list(event["importance"]["reason_codes"]),
                    "summary": _important_summary(event["payload"]),
                }

            for relationship in event["relationships"]:
                relationship_type = relationship["type"]
                relationship_key = relationship["key"]
                info = relationships.setdefault(relationship_type, {}).setdefault(
                    relationship_key,
                    {
                        "interaction_count": 0,
                        "last_seen_at": "",
                        "significant_event_ids": [],
                        "metadata": _default_relationship_metadata(),
                    },
                )
                info["interaction_count"] += 1
                info["last_seen_at"] = event["timestamp"]
                info["metadata"] = _update_relationship_metadata(
                    info["metadata"],
                    event,
                    is_important=is_important,
                )
                if event_id in info["metadata"]["keynote_event_ids"] and event_id not in info["significant_event_ids"]:
                    info["significant_event_ids"].append(event_id)

        return {
            "search": {
                "terms": {term: search_terms[term] for term in sorted(search_terms)},
                "topics": {topic: search_topics[topic] for topic in sorted(search_topics)},
                "events": {event_id: search_events[event_id] for event_id in sorted(search_events)},
            },
            "important": {
                "event_ids": important_event_ids,
                "events": {event_id: important_events[event_id] for event_id in sorted(important_events)},
            },
            "relationships": {
                relationship_type: {
                    relationship_key: relationships[relationship_type][relationship_key]
                    for relationship_key in sorted(relationships[relationship_type])
                }
                for relationship_type in sorted(relationships)
            },
        }

    def _rebuild_indexes_from_journal(
        self,
        session_id: str,
        *,
        expected_last_sequence: int,
        expected_last_ciphertext_sha256: str,
        persist: bool,
    ) -> dict[str, Any]:
        events, _ = self._load_verified_journal(
            session_id,
            expected_last_sequence=expected_last_sequence,
            expected_last_ciphertext_sha256=expected_last_ciphertext_sha256,
        )
        indexes = self._build_indexes_from_events(events)
        if persist:
            self._write_indexes(session_id, indexes)
        return indexes

    def _recover_state_if_needed(self, session_id: str, state: dict[str, Any]) -> dict[str, Any]:
        events, summary = self._load_verified_journal(
            session_id,
            expected_last_sequence=None,
            expected_last_ciphertext_sha256=None,
        )
        if summary["last_sequence"] == 0:
            if state["last_sequence"] != 0 or state["last_ciphertext_sha256"] != "":
                raise ValueError("private memory state exceeds verified journal")
            return state

        if state["last_sequence"] > summary["last_sequence"]:
            raise ValueError("private memory state exceeds verified journal")
        if (
            state["last_sequence"] == summary["last_sequence"]
            and state["last_ciphertext_sha256"] == summary["last_ciphertext_sha256"]
        ):
            return state

        recovered_state = {
            "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
            "owner_agent_id": self.agent_id,
            "session_id": session_id,
            "started_at": state["started_at"] if state["started_at"] else events[0]["timestamp"],
            "updated_at": events[-1]["timestamp"],
            "last_sequence": summary["last_sequence"],
            "last_ciphertext_sha256": summary["last_ciphertext_sha256"],
            "indexes_need_rebuild": True,
        }
        self._write_state(session_id, recovered_state)
        return recovered_state

    def _load_verified_journal(
        self,
        session_id: str,
        *,
        expected_last_sequence: int | None,
        expected_last_ciphertext_sha256: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        journal_root = self._journal_root(session_id)
        self._assert_not_symlink_or_outside(journal_root, field_name="journal_root", allow_missing=True)
        files = sorted(journal_root.glob("*.event.enc")) if journal_root.exists() else []
        expected_file_count = len(files) if expected_last_sequence is None else expected_last_sequence
        expected_names = [f"{sequence:06d}.event.enc" for sequence in range(1, expected_file_count + 1)]
        actual_names = [path.name for path in files]
        if actual_names != expected_names:
            raise ValueError("private memory journal contains extra, missing, or reordered sequence files")

        previous_ciphertext_sha256 = ""
        seen_event_ids: set[str] = set()
        seen_ciphertext_digests: set[str] = set()
        events: list[dict[str, Any]] = []
        for expected_sequence, path in enumerate(files, start=1):
            self._assert_not_symlink_or_outside(path, field_name="journal_event_path", allow_missing=False)
            try:
                event_record = json.loads(path.read_text("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("private memory journal metadata is invalid") from exc
            if not isinstance(event_record, dict) or set(event_record.keys()) != _EVENT_RECORD_KEYS:
                raise ValueError("private memory journal metadata shape mismatch")
            if event_record["schema_version"] != MEMORY_VAULT_SCHEMA_VERSION:
                raise ValueError("private memory journal schema mismatch")
            if event_record["owner_agent_id"] != self.agent_id:
                raise ValueError("private memory journal owner mismatch")
            if event_record["session_id"] != session_id:
                raise ValueError("private memory journal session mismatch")
            if int(event_record["sequence"]) != expected_sequence:
                raise ValueError("private memory journal sequence metadata mismatch")
            if path.name != f"{expected_sequence:06d}.event.enc":
                raise ValueError("private memory journal file name mismatch")
            if str(event_record["previous_ciphertext_sha256"]) != previous_ciphertext_sha256:
                raise ValueError("private memory journal hash chain break")

            event_id = str(event_record["event_id"])
            event_type = str(event_record["event_type"])
            event_timestamp = str(event_record["timestamp"])
            event_payload = decrypt_json(
                event_record["envelope"],
                self._key,
                event_aad(
                    agent_id=self.agent_id,
                    session_id=session_id,
                    sequence=expected_sequence,
                    event_id=event_id,
                    event_type=event_type,
                    timestamp=event_timestamp,
                    previous_ciphertext_sha256=previous_ciphertext_sha256,
                ),
            )
            expected_event = normalize_memory_event(
                agent_id=self.agent_id,
                session_id=session_id,
                sequence=expected_sequence,
                event_type=event_type,
                payload=event_payload["payload"],
                timestamp=event_timestamp,
            )
            if event_payload != expected_event:
                raise ValueError("private memory journal normalized event mismatch")
            if event_payload["event_id"] != event_id:
                raise ValueError("private memory journal event identity mismatch")

            ciphertext_sha256 = str(event_record["envelope"]["ciphertext_sha256"])
            if event_id in seen_event_ids or ciphertext_sha256 in seen_ciphertext_digests:
                raise ValueError("private memory journal replay detected")
            seen_event_ids.add(event_id)
            seen_ciphertext_digests.add(ciphertext_sha256)
            previous_ciphertext_sha256 = ciphertext_sha256
            events.append(event_payload)

        actual_last_sequence = len(events)
        if actual_last_sequence == 0 and expected_last_ciphertext_sha256 not in (None, ""):
            raise ValueError("private memory journal empty session hash mismatch")
        if expected_last_sequence is not None and actual_last_sequence != expected_last_sequence:
            raise ValueError("private memory journal sequence mismatch")
        if expected_last_ciphertext_sha256 is not None and actual_last_sequence > 0 and previous_ciphertext_sha256 != expected_last_ciphertext_sha256:
            raise ValueError("private memory journal last ciphertext hash mismatch")

        return events, {
            "verified": True,
            "owner_agent_id": self.agent_id,
            "session_id": session_id,
            "event_count": len(events),
            "last_sequence": actual_last_sequence,
            "last_ciphertext_sha256": previous_ciphertext_sha256,
        }

    def _read_attestation(self, *, verification_key: bytes) -> dict[str, Any]:
        self._assert_not_symlink_or_outside(self.attestation_path, field_name="attestation_path", allow_missing=False)
        try:
            attestation = json.loads(self.attestation_path.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("private memory vault attestation metadata conflict") from exc
        manifest_sha256 = _sha256_file(self.manifest_path)
        validated = _validate_attestation_payload(
            attestation,
            owner_agent_id=self.agent_id,
            key_ref=self.key_ref,
            manifest_sha256=manifest_sha256,
        )
        verify_attestation(
            {key: value for key, value in validated.items() if key != "signature"},
            validated["signature"],
            verification_key,
        )
        return validated


def validate_private_memory_descriptor(
    descriptor: dict[str, Any],
    *,
    expected_agent_id: str,
    vault_root: Path | None = None,
    verification_key: bytes | None = None,
) -> dict[str, Any]:
    if not isinstance(descriptor, dict):
        raise ValueError("private memory descriptor must be an object")

    normalized_owner = normalize_agent_id(expected_agent_id)
    if descriptor.get("schema_version") != MEMORY_VAULT_SCHEMA_VERSION:
        raise ValueError("private memory descriptor schema_version mismatch")
    if descriptor.get("owner_agent_id") != normalized_owner:
        raise ValueError("private memory descriptor owner_agent_id mismatch")
    if descriptor.get("verified") is not True:
        raise ValueError("private memory descriptor must be verified")

    ciphertext_ref = str(descriptor.get("ciphertext_ref") or "").strip()
    key_ref = str(descriptor.get("key_ref") or "").strip()
    attestation_sha256 = str(descriptor.get("attestation_sha256") or "").strip()
    if not ciphertext_ref:
        raise ValueError("private memory descriptor ciphertext_ref is required")
    if not key_ref:
        raise ValueError("private memory descriptor key_ref is required")
    if not _HEX_64_RE.fullmatch(attestation_sha256):
        raise ValueError("private memory descriptor attestation_sha256 must be 64 hex characters")

    validated = {
        "schema_version": MEMORY_VAULT_SCHEMA_VERSION,
        "owner_agent_id": normalized_owner,
        "ciphertext_ref": ciphertext_ref,
        "attestation_sha256": attestation_sha256,
        "key_ref": key_ref,
        "verified": True,
    }
    if vault_root is None:
        return validated
    if verification_key is None:
        raise ValueError("private memory descriptor verification_key is required with vault_root")

    lexical_root = Path(vault_root)
    resolved_root = lexical_root.resolve(strict=False)
    lexical_agent_root = lexical_root / normalized_owner
    if _is_reparse_or_symlink(lexical_agent_root):
        raise ValueError("private memory descriptor owner directory reparse or symlink rejected")

    resolved_owner_root = lexical_agent_root.resolve(strict=False)
    expected_resolved_owner_root = resolved_root / normalized_owner
    if resolved_owner_root != expected_resolved_owner_root:
        raise ValueError("private memory descriptor owner root rebind rejected")
    if not _is_parent_or_self(resolved_root, resolved_owner_root):
        raise ValueError("private memory descriptor owner root escapes vault_root")

    lexical_manifest_path = Path(ciphertext_ref)
    if lexical_manifest_path != lexical_agent_root / "vault.manifest.enc":
        raise ValueError("private memory descriptor ciphertext_ref path mismatch")
    if _is_reparse_or_symlink(lexical_manifest_path):
        raise ValueError("private memory descriptor manifest reparse or symlink rejected")
    manifest_path = lexical_manifest_path.resolve(strict=False)
    expected_manifest_path = expected_resolved_owner_root / "vault.manifest.enc"
    if manifest_path != expected_manifest_path:
        raise ValueError("private memory descriptor ciphertext_ref path rebind rejected")
    try:
        lexical_manifest_path.relative_to(lexical_agent_root)
    except ValueError as exc:
        raise ValueError("private memory descriptor path escape rejected") from exc
    if not _is_parent_or_self(resolved_root, manifest_path):
        raise ValueError("private memory descriptor path escape rejected")
    if not lexical_manifest_path.exists():
        raise ValueError("private memory descriptor manifest is missing")

    lexical_attestation_path = lexical_agent_root / "vault.attestation.json"
    if _is_reparse_or_symlink(lexical_attestation_path):
        raise ValueError("private memory descriptor attestation reparse or symlink rejected")
    attestation_path = lexical_attestation_path.resolve(strict=False)
    expected_attestation_path = expected_resolved_owner_root / "vault.attestation.json"
    if attestation_path != expected_attestation_path:
        raise ValueError("private memory descriptor attestation path rebind rejected")
    if not _is_parent_or_self(resolved_root, attestation_path):
        raise ValueError("private memory descriptor path escape rejected")
    if not lexical_attestation_path.exists():
        raise ValueError("private memory descriptor attestation is missing")
    if _sha256_file(lexical_attestation_path) != attestation_sha256:
        raise ValueError("private memory descriptor attestation digest mismatch")

    try:
        attestation = json.loads(lexical_attestation_path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("private memory descriptor attestation metadata mismatch") from exc
    if not isinstance(attestation, dict):
        raise ValueError("private memory descriptor attestation metadata mismatch")
    if not _HEX_64_RE.fullmatch(str(attestation.get("manifest_sha256", ""))):
        raise ValueError("private memory descriptor attestation manifest hash mismatch")
    validated_attestation = _validate_attestation_payload(
        attestation,
        owner_agent_id=normalized_owner,
        key_ref=key_ref,
        manifest_sha256=_sha256_file(lexical_manifest_path),
    )
    verify_attestation(
        {key: value for key, value in validated_attestation.items() if key != "signature"},
        validated_attestation["signature"],
        verification_key,
    )
    return validated
