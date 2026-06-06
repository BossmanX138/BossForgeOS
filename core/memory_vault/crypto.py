from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MEMORY_VAULT_SCHEMA_VERSION = "1.0"
_MEMORY_KEY_CONTEXT = "private-memory-v1"
_VALID_AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_VALID_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MEMORY_KEY_ERROR = "memory key must be bytes-like and exactly 32 bytes"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _coerce_memory_key(key: bytes | bytearray | memoryview) -> bytes:
    if isinstance(key, memoryview):
        key_bytes = key.tobytes()
    elif isinstance(key, (bytes, bytearray)):
        key_bytes = bytes(key)
    else:
        raise ValueError(_MEMORY_KEY_ERROR)
    if len(key_bytes) != 32:
        raise ValueError(_MEMORY_KEY_ERROR)
    return key_bytes


def normalize_agent_id(value: str) -> str:
    agent_id = str(value or "").strip()
    if not agent_id or agent_id in {".", ".."}:
        raise ValueError("agent_id must be a normalized path-safe identifier")
    if agent_id != agent_id.lower():
        raise ValueError("agent_id must already be lowercase")
    if "/" in agent_id or "\\" in agent_id:
        raise ValueError("agent_id must be a normalized path-safe identifier")
    if not _VALID_AGENT_ID_RE.fullmatch(agent_id):
        raise ValueError("agent_id must be a normalized path-safe identifier")
    return agent_id


def _normalize_path_safe_id(value: str, *, field_name: str) -> str:
    identifier = str(value or "").strip()
    if not identifier or identifier in {".", ".."}:
        raise ValueError(f"{field_name} must be a normalized path-safe identifier")
    if "/" in identifier or "\\" in identifier:
        raise ValueError(f"{field_name} must be a normalized path-safe identifier")
    if not _VALID_SESSION_ID_RE.fullmatch(identifier):
        raise ValueError(f"{field_name} must be a normalized path-safe identifier")
    return identifier


def derive_memory_key(node_secret: str, agent_id: str) -> bytes:
    secret = str(node_secret or "")
    if not secret:
        raise ValueError("node secret is required")
    normalized = normalize_agent_id(agent_id)
    material = f"{secret}:{normalized}:{_MEMORY_KEY_CONTEXT}".encode("utf-8")
    return hashlib.sha256(material).digest()


def encrypt_bytes(plaintext: bytes, key: bytes, aad: bytes) -> dict[str, str | int]:
    aes = AESGCM(_coerce_memory_key(key))
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, plaintext, aad)
    return {
        "version": 1,
        "alg": "AES-256-GCM",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
    }


def decrypt_bytes(envelope: dict[str, Any], key: bytes, aad: bytes) -> bytes:
    try:
        aes_key = _coerce_memory_key(key)
        if not isinstance(envelope, Mapping):
            raise ValueError("memory envelope authentication failed")
        if int(envelope.get("version", 0)) != 1:
            raise ValueError("memory envelope authentication failed")
        if str(envelope.get("alg", "")) != "AES-256-GCM":
            raise ValueError("unsupported memory envelope algorithm")
        nonce = base64.b64decode(str(envelope["nonce_b64"]), validate=True)
        if len(nonce) != 12:
            raise ValueError("memory envelope authentication failed")
        ciphertext = base64.b64decode(str(envelope["ciphertext_b64"]), validate=True)
        digest = str(envelope["ciphertext_sha256"])
        if not _DIGEST_RE.fullmatch(digest):
            raise ValueError("memory envelope authentication failed")
        if hashlib.sha256(ciphertext).hexdigest() != digest:
            raise ValueError("memory envelope digest mismatch")
        plaintext = AESGCM(aes_key).decrypt(nonce, ciphertext, aad)
        return plaintext
    except ValueError as exc:
        if str(exc) == _MEMORY_KEY_ERROR:
            raise
        raise ValueError("memory envelope authentication failed") from exc
    except (KeyError, TypeError, InvalidTag, binascii.Error) as exc:
        raise ValueError("memory envelope authentication failed") from exc


def event_aad(
    *,
    agent_id: str,
    session_id: str,
    sequence: int,
    event_id: str,
    event_type: str,
    timestamp: str,
    previous_ciphertext_sha256: str,
) -> bytes:
    return canonical_json(
        {
            "agent_id": normalize_agent_id(agent_id),
            "event_id": str(event_id),
            "event_type": str(event_type).strip(),
            "previous_ciphertext_sha256": str(previous_ciphertext_sha256),
            "sequence": int(sequence),
            "session_id": _normalize_path_safe_id(session_id, field_name="session_id"),
            "timestamp": str(timestamp).strip(),
        }
    )


def encrypt_json(payload: dict[str, Any], key: bytes, aad: bytes) -> dict[str, str | int]:
    if not isinstance(payload, dict):
        raise ValueError("memory payload must be an object")
    return encrypt_bytes(canonical_json(payload), key, aad)


def decrypt_json(envelope: dict[str, Any], key: bytes, aad: bytes) -> dict[str, Any]:
    plaintext = decrypt_bytes(envelope, key, aad)
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("memory envelope authentication failed") from exc
    if not isinstance(payload, dict):
        raise ValueError("memory payload must be an object")
    return payload


def sign_attestation(payload: dict[str, Any], key: bytes) -> str:
    if not isinstance(payload, dict):
        raise ValueError("memory attestation payload must be an object")
    mac = hmac.new(key, canonical_json(payload), hashlib.sha256)
    return mac.hexdigest()


def verify_attestation(payload: dict[str, Any], signature: str, key: bytes) -> None:
    expected = sign_attestation(payload, key)
    if not hmac.compare_digest(expected, str(signature)):
        raise ValueError("memory attestation signature mismatch")


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(target)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise


def atomic_write_json(path: str | Path, payload: object) -> None:
    atomic_write_bytes(path, canonical_json(payload))
