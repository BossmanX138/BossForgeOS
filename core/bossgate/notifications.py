"""Canonical, authenticated BossGate notification and reply wire envelopes.

Previews must be redacted by the caller. These codecs never infer redaction.
Replay sets are caller-owned and must be shared/persisted at the receiving gate.
"""
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import re
import secrets
from typing import Any
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag

from core.bossgate import decrypt_json_payload, encrypt_json_payload

NOTIFICATION_SCHEMA = "bosscrafts.bossgate.notification.v1"
REPLY_SCHEMA = "bosscrafts.bossgate.reply.v1"
SEVERITIES = frozenset({"info", "warning", "error", "critical"})
USER_FACING_EVENT_TYPES = frozenset({
    "repair.approval_requested", "repair.implementation_started", "repair.implementation_completed",
    "repair.verification_failed", "repair.needs_decision", "repair.backup_failed", "delivery.recovered",
})
MAX_PREVIEW_CHARACTERS = 2048
MAX_SEALED_PAYLOAD_BYTES = 1048576
_PREVIEW_FIELDS = {"title", "project_name", "summary", "action"}
_COMMON_FIELDS = {"schema", "message_id", "correlation_id", "source_gate", "created_at", "expires_at",
                  "sealed_payload", "payload_hash", "nonce", "key_id", "signature"}
_NOTIFICATION_FIELDS = _COMMON_FIELDS | {"event_type", "severity", "recipient_account_id", "preview"}
_REPLY_FIELDS = _COMMON_FIELDS | {"parent_message_id", "target_gate", "reply_type"}
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Sorted compact ASCII JSON, matching the existing BossGate JSON convention."""
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _utc_now(at: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if at is None else at
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("at must be an offset-aware datetime")
    return value.astimezone(timezone.utc)


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        raise ValueError(f"invalid UTC Z timestamp: {field}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid UTC Z timestamp: {field}") from exc


def _uuid(value: str, field: str) -> None:
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"invalid UUID: {field}") from exc


def _resolve_key(secret_keys: str | Mapping[str, str], key_id: str) -> str:
    # New envelopes require an exact key ID; no silent fallback across rotation.
    secret = secret_keys.get(key_id) if isinstance(secret_keys, Mapping) else secret_keys
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("no key available for key_id")
    return secret


def _check_structure(envelope: Mapping[str, Any], schema: str) -> None:
    if not isinstance(envelope, Mapping):
        raise ValueError("envelope must be an object")
    fields = _NOTIFICATION_FIELDS if schema == NOTIFICATION_SCHEMA else _REPLY_FIELDS
    if set(envelope) != fields:
        raise ValueError("missing or unknown envelope fields")
    for field in fields - {"preview"}:
        if not isinstance(envelope[field], str) or not envelope[field].strip():
            raise ValueError(f"invalid string: {field}")
    if envelope["schema"] != schema:
        raise ValueError("unsupported schema")
    for field in ("message_id", "correlation_id"):
        _uuid(envelope[field], field)
    if schema == REPLY_SCHEMA:
        _uuid(envelope["parent_message_id"], "parent_message_id")
    else:
        if envelope["severity"] not in SEVERITIES:
            raise ValueError("invalid severity")
        if envelope["event_type"] not in USER_FACING_EVENT_TYPES:
            raise ValueError("invalid event_type")
        preview = envelope["preview"]
        if not isinstance(preview, dict) or set(preview) != _PREVIEW_FIELDS:
            raise ValueError("missing or unknown preview fields")
        if any(not isinstance(value, str) for value in preview.values()):
            raise ValueError("preview values must be strings")
        if len(canonical_json_bytes(preview).decode("utf-8")) > MAX_PREVIEW_CHARACTERS:
            raise ValueError("preview exceeds 2048 serialized characters")
    if len(envelope["sealed_payload"].encode("utf-8")) > MAX_SEALED_PAYLOAD_BYTES:
        raise ValueError("sealed_payload exceeds 1048576 bytes")
    for field in ("payload_hash", "signature"):
        if not _HEX_DIGEST.fullmatch(envelope[field]):
            raise ValueError(f"invalid SHA-256 digest: {field}")
    created = _timestamp(envelope["created_at"], "created_at")
    expires = _timestamp(envelope["expires_at"], "expires_at")
    if expires <= created:
        raise ValueError("expires_at must follow created_at")


def _signature(envelope: Mapping[str, Any], secret: str) -> str:
    unsigned = {key: value for key, value in envelope.items() if key != "signature"}
    return hmac.new(secret.encode("utf-8"), canonical_json_bytes(unsigned), hashlib.sha256).hexdigest()


def _check_detail(detail: dict[str, Any]) -> None:
    """Reject invalid JSON numbers and explicitly named command-code material."""
    canonical_json_bytes(detail)

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized.endswith(("commandcode", "commandcodes")):
                    raise ValueError("command-code fields are prohibited in BossGate detail")
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(detail)


def _strict_base64(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ValueError("Base64 value must be a string")
    decoded = base64.b64decode(value.encode("ascii"), validate=True)
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("noncanonical Base64 encoding")
    return decoded


def _check_sealed_blob(encoded: str, key_id: str) -> None:
    """Enforce the new wire contract before using the permissive legacy decoder."""
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate encrypted blob field")
            result[key] = value
        return result

    blob = json.loads(_strict_base64(encoded).decode("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(blob, dict) or set(blob) != {"version", "alg", "key_id", "nonce_b64", "ciphertext_b64"}:
        raise ValueError("missing or unknown encrypted blob fields")
    if type(blob["version"]) is not int or blob["version"] != 1:
        raise ValueError("unsupported encrypted blob version")
    if blob["alg"] != "AES-256-GCM" or blob["key_id"] != key_id:
        raise ValueError("encrypted blob algorithm or key ID mismatch")
    if len(_strict_base64(blob["nonce_b64"])) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    if len(_strict_base64(blob["ciphertext_b64"])) < 16:
        raise ValueError("AES-GCM ciphertext must include an authentication tag")


def _build(*, fields: dict[str, Any], detail: dict[str, Any], secret_key: str, key_id: str,
           message_id: str | None, expires_in_seconds: int, at: datetime | None) -> dict[str, Any]:
    if not isinstance(detail, dict):
        raise ValueError("detail must be an object")
    _check_detail(detail)
    if type(expires_in_seconds) is not int or expires_in_seconds <= 0:
        raise ValueError("expires_in_seconds must be a positive integer")
    if not isinstance(key_id, str) or not key_id or key_id != key_id.strip():
        raise ValueError("key_id must be a nonempty string without surrounding whitespace")
    secret = _resolve_key(secret_key, key_id)
    now = _utc_now(at)
    envelope = {**fields, "message_id": str(uuid4()) if message_id is None else message_id,
                "created_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(seconds=expires_in_seconds)).isoformat().replace("+00:00", "Z"),
                "nonce": secrets.token_hex(32), "key_id": key_id,
                "sealed_payload": encrypt_json_payload(detail, secret, key_id), "signature": "0" * 64}
    envelope["payload_hash"] = hashlib.sha256(envelope["sealed_payload"].encode("utf-8")).hexdigest()
    _check_structure(envelope, fields["schema"])
    envelope["signature"] = _signature(envelope, secret)
    return envelope


def build_notification_envelope(*, event_type: str, severity: str, source_gate: str,
    recipient_account_id: str, preview: dict[str, str], detail: dict[str, Any],
    secret_key: str, key_id: str, correlation_id: str, message_id: str | None = None,
    expires_in_seconds: int = 86400, at: datetime | None = None) -> dict[str, Any]:
    return _build(fields={"schema": NOTIFICATION_SCHEMA, "event_type": event_type, "severity": severity,
                         "source_gate": source_gate, "recipient_account_id": recipient_account_id,
                         "preview": dict(preview), "correlation_id": correlation_id},
                  detail=detail, secret_key=secret_key, key_id=key_id, message_id=message_id,
                  expires_in_seconds=expires_in_seconds, at=at)


def build_reply_envelope(*, parent_message_id: str, correlation_id: str,
    source_gate: str, target_gate: str, reply_type: str, detail: dict[str, Any],
    secret_key: str, key_id: str, message_id: str | None = None,
    expires_in_seconds: int = 604800, at: datetime | None = None) -> dict[str, Any]:
    return _build(fields={"schema": REPLY_SCHEMA, "parent_message_id": parent_message_id,
                         "correlation_id": correlation_id, "source_gate": source_gate,
                         "target_gate": target_gate, "reply_type": reply_type},
                  detail=detail, secret_key=secret_key, key_id=key_id, message_id=message_id,
                  expires_in_seconds=expires_in_seconds, at=at)


def _authenticate(envelope: Mapping[str, Any], secret_keys: str | Mapping[str, str], schema: str) -> dict[str, Any]:
    _check_structure(envelope, schema)
    expected_hash = hashlib.sha256(envelope["sealed_payload"].encode("utf-8")).hexdigest()
    if not hmac.compare_digest(envelope["payload_hash"], expected_hash):
        raise ValueError("payload hash mismatch")
    secret = _resolve_key(secret_keys, envelope["key_id"])
    if not hmac.compare_digest(envelope["signature"], _signature(envelope, secret)):
        raise ValueError("signature mismatch")
    try:
        _check_sealed_blob(envelope["sealed_payload"], envelope["key_id"])
        # Resolve by the authenticated outer key ID, never an untrusted inner key ID.
        detail = decrypt_json_payload(envelope["sealed_payload"], secret)
        _check_detail(detail)
        return detail
    except (ValueError, TypeError, KeyError, UnicodeError, InvalidTag) as exc:
        raise ValueError("invalid sealed payload or encryption key") from exc


def _validate(envelope: Mapping[str, Any], secret_keys: str | Mapping[str, str], schema: str,
              replay_tokens: set[str] | None, at: datetime | None) -> tuple[bool, str]:
    try:
        _authenticate(envelope, secret_keys, schema)
        now = _utc_now(at)
        if now < _timestamp(envelope["created_at"], "created_at"):
            raise ValueError("envelope created in the future")
        if now >= _timestamp(envelope["expires_at"], "expires_at"):
            raise ValueError("envelope expired")
        if replay_tokens is not None:
            token = hashlib.sha256(canonical_json_bytes({"source_gate": envelope["source_gate"],
                                                       "nonce": envelope["nonce"]})).hexdigest()
            if token in replay_tokens:
                raise ValueError("replay detected: nonce was already consumed")
            replay_tokens.add(token)
        return True, "ok"
    except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
        return False, str(exc)


def validate_notification_envelope(envelope: Mapping[str, Any],
    secret_keys: str | Mapping[str, str], replay_tokens: set[str] | None = None,
    at: datetime | None = None) -> tuple[bool, str]:
    return _validate(envelope, secret_keys, NOTIFICATION_SCHEMA, replay_tokens, at)


def decrypt_notification_detail(envelope: Mapping[str, Any],
    secret_keys: str | Mapping[str, str]) -> dict[str, Any]:
    """Authenticate and decrypt stored detail, including historical/expired messages.

    Delivery acceptance must separately call validate_notification_envelope for
    time and replay checks. Reading history does not consume a delivery nonce.
    """
    return _authenticate(envelope, secret_keys, NOTIFICATION_SCHEMA)


def validate_reply_envelope(envelope: Mapping[str, Any],
    secret_keys: str | Mapping[str, str], replay_tokens: set[str] | None = None,
    at: datetime | None = None) -> tuple[bool, str]:
    return _validate(envelope, secret_keys, REPLY_SCHEMA, replay_tokens, at)
