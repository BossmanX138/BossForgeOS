import json
from pathlib import Path
from typing import Any, Dict

from core.connectors.bossgate_connector import decrypt_json_payload, encrypt_json_payload


PROFILE_STORE_VERSION = 1
PROFILE_STORE_KIND = "bossforge-agent-profile-store"


def _build_secret(node_id: str) -> str:
    return f"{str(node_id).strip()}:agent-profiles:v1"


def load_agent_profiles_store(path: Path, node_id: str) -> tuple[Dict[str, Dict[str, Any]], bool]:
    if not path.exists():
        return {}, False

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, False

    if isinstance(raw, dict) and raw.get("kind") == PROFILE_STORE_KIND:
        encrypted_payload = str(raw.get("encrypted_payload", "")).strip()
        if not encrypted_payload:
            return {}, False
        try:
            payload = decrypt_json_payload(encrypted_payload, secret_key=_build_secret(node_id))
        except Exception:
            return {}, False
        profiles = payload.get("profiles")
        if not isinstance(profiles, dict):
            return {}, False
        return _normalize_profiles(profiles), False

    if isinstance(raw, dict):
        return _normalize_profiles(raw), True
    return {}, False


def save_agent_profiles_store(path: Path, profiles: Dict[str, Dict[str, Any]], node_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PROFILE_STORE_VERSION,
        "profiles": profiles,
    }
    sealed = {
        "version": PROFILE_STORE_VERSION,
        "kind": PROFILE_STORE_KIND,
        "key_id": "node-local-agent-profiles",
        "encrypted_payload": encrypt_json_payload(
            payload,
            secret_key=_build_secret(node_id),
            key_id="node-local-agent-profiles",
        ),
    }
    path.write_text(json.dumps(sealed, indent=2), encoding="utf-8")


def _normalize_profiles(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        normalized_key = str(key).strip().lower()
        if not normalized_key:
            continue
        out[normalized_key] = dict(value)
    return out
