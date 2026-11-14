"""Ed25519 approval proofs; command-code verification belongs to the issuer.

Recipients need only trusted public keys. Callers own the persisted nonce set
and must serialize verify/consume operations when accepting concurrent requests.
"""
import base64
from collections.abc import Mapping
from datetime import datetime, timedelta
import secrets
from typing import Any

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from core.bossgate.notifications import (
    canonical_json_bytes, _HEX_DIGEST, _strict_base64, _timestamp, _utc_now,
)

REPAIR_APPROVAL_SCHEMA = "bosscrafts.bossgate.repair-approval.v1"
_BINDING_FIELDS = frozenset({"account_id", "device_id", "source_gate", "repair_job_id",
                             "proposal_version", "proposal_digest", "project_fingerprint", "action"})
_ASSERTION_FIELDS = _BINDING_FIELDS | {"schema", "created_at", "expires_at", "nonce", "key_id", "signature"}


def _check_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"invalid string: {field}")


def _check_binding(binding: Mapping[str, str]) -> None:
    if not isinstance(binding, Mapping) or set(binding) != _BINDING_FIELDS:
        raise ValueError("missing or unknown approval binding fields")
    for field in _BINDING_FIELDS:
        _check_string(binding[field], field)
    if binding["action"] != "approve_repair":
        raise ValueError("unsupported approval action")
    for field in ("proposal_digest", "project_fingerprint"):
        if not _HEX_DIGEST.fullmatch(binding[field]):
            raise ValueError(f"invalid SHA-256 digest: {field}")


def _unsigned(assertion: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes({key: value for key, value in assertion.items() if key != "signature"})


def _check_structure(assertion: Mapping[str, Any]) -> None:
    if not isinstance(assertion, Mapping) or set(assertion) != _ASSERTION_FIELDS:
        raise ValueError("missing or unknown approval assertion fields")
    for field in _ASSERTION_FIELDS:
        _check_string(assertion[field], field)
    if assertion["schema"] != REPAIR_APPROVAL_SCHEMA:
        raise ValueError("unsupported approval schema")
    _check_binding({key: assertion[key] for key in _BINDING_FIELDS})
    created = _timestamp(assertion["created_at"], "created_at")
    expires = _timestamp(assertion["expires_at"], "expires_at")
    if not timedelta(0) < expires - created <= timedelta(seconds=60):
        raise ValueError("approval lifetime must be greater than zero and at most 60 seconds")
    if len(_strict_base64(assertion["signature"])) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")


def build_repair_approval_assertion(*, binding: Mapping[str, str],
    private_key_pem: str, key_id: str, nonce: str | None = None,
    ttl_seconds: int = 60, at: datetime | None = None) -> dict[str, Any]:
    """Sign exact approval bindings after the issuer has verified authorization."""
    _check_binding(binding)
    _check_string(key_id, "key_id")
    if type(ttl_seconds) is not int:
        raise ValueError("ttl_seconds must be an integer")
    if not isinstance(private_key_pem, str):
        raise ValueError("private_key_pem must be a PEM string")
    private_key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("approval private key must be Ed25519")
    now = _utc_now(at)
    assertion = {**binding, "schema": REPAIR_APPROVAL_SCHEMA, "key_id": key_id,
                 "nonce": secrets.token_hex(32) if nonce is None else nonce,
                 "created_at": now.isoformat().replace("+00:00", "Z"),
                 "expires_at": (now + timedelta(seconds=max(1, min(60, ttl_seconds)))).isoformat().replace("+00:00", "Z"),
                 "signature": base64.b64encode(bytes(64)).decode("ascii")}
    _check_structure(assertion)
    assertion["signature"] = base64.b64encode(private_key.sign(_unsigned(assertion))).decode("ascii")
    return assertion


def verify_repair_approval_assertion(assertion: Mapping[str, Any],
    public_keys: Mapping[str, str], expected: Mapping[str, str],
    consumed_nonces: set[str] | None = None,
    at: datetime | None = None) -> tuple[bool, str]:
    """Authenticate, bind, and accept a fresh proof, consuming its nonce last.

    Omitting consumed_nonces performs verification without replay persistence.
    The trusted key map and complete expected bindings must come from the caller.
    """
    try:
        _check_structure(assertion)
        _check_binding(expected)
        if not isinstance(public_keys, Mapping):
            raise ValueError("public_keys must be a key ID mapping")
        pem = public_keys.get(assertion["key_id"])
        if not isinstance(pem, str) or not pem.strip():
            raise ValueError("no public key available for key_id")
        public_key = serialization.load_pem_public_key(pem.encode("ascii"))
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("approval public key must be Ed25519")
        public_key.verify(_strict_base64(assertion["signature"]), _unsigned(assertion))
        for field in _BINDING_FIELDS:
            if assertion[field] != expected[field]:
                raise ValueError(f"approval binding mismatch: {field}")
        now = _utc_now(at)
        if now < _timestamp(assertion["created_at"], "created_at"):
            raise ValueError("approval created in the future")
        if now >= _timestamp(assertion["expires_at"], "expires_at"):
            raise ValueError("approval expired")
        if consumed_nonces is not None:
            if assertion["nonce"] in consumed_nonces:
                raise ValueError("replay detected: approval nonce was already consumed")
            consumed_nonces.add(assertion["nonce"])
        return True, "ok"
    except InvalidSignature:
        return False, "approval signature mismatch"
    except (ValueError, TypeError, OverflowError, UnicodeError, UnsupportedAlgorithm) as exc:
        return False, str(exc)
