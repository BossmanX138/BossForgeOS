import socket
import json
import threading
import time
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlparse
from urllib import request
import re
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BOSSGATE_PORT = 50505
BOSSGATE_BEACON = b'BOSSGATE-ASS-PAIRING'
BOSSGATE_BEACON_PREFIX = b'BOSSGATE-PRESENCE:'

ALLOWED_TRAVEL_TARGET_TYPES = {
    "bossgate_connector",
    "ass",
    "bossforgeos",
    "bridgebase_alpha",
}

TARGET_SIGNATURES = {
    "bossgate_connector": (
        "bossgate",
        "bossgate connector",
        "bossgate",
    ),
    "ass": (
        "a.s.s",
        "ass",
        "anvil secured shuttle",
    ),
    "bossforgeos": (
        "bossforgeos",
        "bossforge os",
    ),
    "bridgebase_alpha": (
        "bridgebase_alpha",
        "bridgebase alpha",
    ),
}

METADATA_VISIBILITY_LEVELS = {
    "none",
    "id_card_only",
    "model_card_only",
    "id_and_model_card",
}

SECURE_ADDRESS_WORDLIST = (
    "anvil", "arc", "atlas", "axiom", "beacon", "blaze", "bridge", "cipher",
    "codemage", "comet", "core", "delta", "ember", "forge", "gate", "glint",
    "haven", "helix", "ion", "jade", "keystone", "lumen", "matrix", "nova",
    "onyx", "orbit", "phoenix", "pulse", "quartz", "quill", "raven", "rune",
    "saber", "sentinel", "shuttle", "sigma", "spark", "spoke", "star", "titan",
    "trace", "vector", "vertex", "warden", "zenith",
)
SECURE_ADDRESS_PATTERN = re.compile(r"^\*(?:[a-z]+(?:\*[a-z]+){6})\*$")


def _normalize_url_for_scan(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"http://{url}"
    return url


def _collect_identity_text(metadata: dict) -> str:
    parts = []
    for key in (
        "server",
        "x-powered-by",
        "x-bossgate-role",
        "x-bossgate-target-type",
        "title",
        "description",
        "name",
    ):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip().lower())
    return "\n".join(parts)


def classify_target_type(metadata: dict) -> str:
    corpus = _collect_identity_text(metadata)
    if not corpus:
        return "unknown"
    for target_type, signatures in TARGET_SIGNATURES.items():
        for signature in signatures:
            if signature in corpus:
                return target_type
    return "unknown"


def is_valid_transfer_target(metadata: dict) -> tuple[bool, str]:
    target_type = classify_target_type(metadata)
    return target_type in ALLOWED_TRAVEL_TARGET_TYPES, target_type


def _normalize_agent_presence(raw_agents: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for item in raw_agents or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip().lower()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "agent_class": str(item.get("agent_class", "prime")).strip().lower() or "prime",
                "bossgate_enabled": bool(item.get("bossgate_enabled", True)),
                "created_by_node": str(item.get("created_by_node", "")).strip(),
                "current_node": str(item.get("current_node", "")).strip(),
                "assistance_requested": bool(item.get("assistance_requested", False)),
                "assistance_reason": str(item.get("assistance_reason", "")).strip(),
            }
        )
    return out


def _build_presence_packet(node_id: str, agents: list[dict] | None = None, target_type: str = "bossgate_connector") -> bytes:
    payload = {
        "version": 1,
        "node_id": str(node_id or "unknown-node").strip(),
        "target_type": str(target_type or "bossgate_connector").strip().lower(),
        "agents": _normalize_agent_presence(agents),
        "timestamp": int(time.time()),
    }
    return BOSSGATE_BEACON_PREFIX + json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _parse_presence_packet(data: bytes, sender_ip: str) -> dict[str, Any] | None:
    if data == BOSSGATE_BEACON:
        return {
            "address": sender_ip,
            "node_id": sender_ip,
            "target_type": "bossgate_connector",
            "agents": [],
            "legacy": True,
        }

    if not data.startswith(BOSSGATE_BEACON_PREFIX):
        return None

    try:
        payload = json.loads(data[len(BOSSGATE_BEACON_PREFIX):].decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    timestamp_raw = payload.get("timestamp")
    timestamp = int(timestamp_raw) if isinstance(timestamp_raw, int) else 0
    return {
        "address": sender_ip,
        "node_id": str(payload.get("node_id", sender_ip)).strip() or sender_ip,
        "target_type": str(payload.get("target_type", "bossgate_connector")).strip().lower() or "bossgate_connector",
        "agents": _normalize_agent_presence(payload.get("agents") if isinstance(payload.get("agents"), list) else []),
        "legacy": False,
        "timestamp": timestamp,
    }


# --- LAN Beacon/Discovery ---
def broadcast_presence(
    node_id: str,
    agents_provider: Callable[[], list[dict]] | None = None,
    interval_seconds: float = 2.0,
    stop_event: threading.Event | None = None,
) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while stop_event is None or not stop_event.is_set():
            agents = agents_provider() if callable(agents_provider) else []
            packet = _build_presence_packet(node_id=node_id, agents=agents, target_type="bossgate_connector")
            s.sendto(packet, ('<broadcast>', BOSSGATE_PORT))
            time.sleep(max(0.2, float(interval_seconds)))
    finally:
        s.close()


def broadcast_beacon(node_id: str | None = None, agents_provider: Callable[[], list[dict]] | None = None):
    node_name = (node_id or socket.gethostname() or "unknown-node").strip()
    broadcast_presence(node_id=node_name, agents_provider=agents_provider)


def listen_for_beacons(timeout=5):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(('', BOSSGATE_PORT))
        s.settimeout(timeout)
        found: dict[tuple[str, str], dict[str, Any]] = {}
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = s.recvfrom(4096)
                parsed = _parse_presence_packet(data=data, sender_ip=addr[0])
                if parsed is not None:
                    found[(parsed["address"], parsed["node_id"])] = parsed
            except socket.timeout:
                break
        return list(found.values())
    finally:
        s.close()


def discover_transfer_targets(timeout=5, assistance_only: bool = False):
    peers = listen_for_beacons(timeout=timeout)
    targets: list[dict[str, Any]] = []
    for peer in peers:
        address = str(peer.get("address", "")).strip()
        node_id = str(peer.get("node_id", address)).strip() or address
        target_type = str(peer.get("target_type", "bossgate_connector")).strip().lower() or "bossgate_connector"
        agents = peer.get("agents") if isinstance(peer.get("agents"), list) else []

        if not agents:
            if assistance_only:
                continue
            targets.append(
                {
                    "address": address,
                    "node_id": node_id,
                    "agent_name": "",
                    "target_type": target_type,
                    "allowed_for_transfer": target_type in ALLOWED_TRAVEL_TARGET_TYPES,
                    "assistance_requested": False,
                    "reason": "validated by BossGate beacon",
                }
            )
            continue

        for agent in agents:
            assistance_requested = bool(agent.get("assistance_requested", False))
            if assistance_only and not assistance_requested:
                continue
            targets.append(
                {
                    "address": address,
                    "node_id": node_id,
                    "agent_name": str(agent.get("name", "")).strip().lower(),
                    "agent_class": str(agent.get("agent_class", "prime")).strip().lower() or "prime",
                    "created_by_node": str(agent.get("created_by_node", "")).strip(),
                    "current_node": str(agent.get("current_node", node_id)).strip() or node_id,
                    "target_type": target_type,
                    "allowed_for_transfer": target_type in ALLOWED_TRAVEL_TARGET_TYPES and bool(agent.get("bossgate_enabled", True)),
                    "assistance_requested": assistance_requested,
                    "assistance_reason": str(agent.get("assistance_reason", "")).strip(),
                    "reason": "agent presence beacon",
                }
            )
    return targets


def _http_get_json(url: str, timeout: float = 2.0):
    req = request.Request(url=url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        headers = {k: v for k, v in resp.headers.items()}
        body = resp.read().decode("utf-8", errors="replace")
    payload = json.loads(body)
    return status, headers, payload


def _http_get_headers(url: str, timeout: float = 2.0):
    req = request.Request(url=url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        headers = {k: v for k, v in resp.headers.items()}
    return status, headers


def _http_options_headers(url: str, timeout: float = 2.0):
    req = request.Request(url=url, method="OPTIONS")
    with request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        headers = {k: v for k, v in resp.headers.items()}
    return status, headers


def generate_secure_address(wordlist: tuple[str, ...] | list[str] | None = None) -> str:
    words = tuple(str(w).strip().lower() for w in (wordlist or SECURE_ADDRESS_WORDLIST) if str(w).strip())
    if len(words) < 7:
        raise ValueError("wordlist must contain at least 7 words")
    selected = [secrets.choice(words) for _ in range(7)]
    return "*" + "*".join(selected) + "*"


def is_valid_secure_address(address: str) -> bool:
    return bool(SECURE_ADDRESS_PATTERN.match((address or "").strip().lower()))


def apply_metadata_visibility_profile(
    profile: str | None,
    agent_id_card: dict[str, Any] | None = None,
    model_card_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_profile = str(profile or "none").strip().lower()
    if normalized_profile not in METADATA_VISIBILITY_LEVELS:
        normalized_profile = "none"

    result: dict[str, Any] = {
        "profile": normalized_profile,
        "agent_id_card": None,
        "model_card_snapshot": None,
    }
    if normalized_profile in {"id_card_only", "id_and_model_card"}:
        result["agent_id_card"] = dict(agent_id_card or {})
    if normalized_profile in {"model_card_only", "id_and_model_card"}:
        result["model_card_snapshot"] = dict(model_card_snapshot or {})
    return result


def _json_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _derive_aes256_key(secret_key: str) -> bytes:
    return hashlib.sha256(str(secret_key).encode("utf-8")).digest()


def build_chunk_manifest(payload: str, chunk_size: int = 65536) -> dict[str, Any]:
    encoded = str(payload).encode("utf-8")
    safe_chunk_size = max(1, int(chunk_size))
    chunks = []
    for index, offset in enumerate(range(0, len(encoded), safe_chunk_size)):
        chunk = encoded[offset : offset + safe_chunk_size]
        chunks.append(
            {
                "index": index,
                "offset": offset,
                "size": len(chunk),
                "sha256": hashlib.sha256(chunk).hexdigest(),
            }
        )
    return {
        "algorithm": "SHA-256",
        "chunk_size": safe_chunk_size,
        "chunk_count": len(chunks),
        "payload_size": len(encoded),
        "chunks": chunks,
    }


def validate_chunk_manifest(payload: str, manifest: dict[str, Any]) -> tuple[bool, str]:
    if str(manifest.get("algorithm", "")).strip().upper() != "SHA-256":
        return False, "unsupported chunk checksum algorithm"
    expected = build_chunk_manifest(payload, chunk_size=int(manifest.get("chunk_size", 0) or 0))
    if int(manifest.get("payload_size", -1)) != expected["payload_size"]:
        return False, "chunk payload size mismatch"
    if int(manifest.get("chunk_count", -1)) != expected["chunk_count"]:
        return False, "chunk count mismatch"
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != expected["chunk_count"]:
        return False, "invalid chunk manifest"
    for index, expected_chunk in enumerate(expected["chunks"]):
        chunk = chunks[index]
        if not isinstance(chunk, dict):
            return False, f"invalid chunk metadata at index {index}"
        for field in ("index", "offset", "size"):
            if int(chunk.get(field, -1)) != expected_chunk[field]:
                return False, f"chunk {field} mismatch at index {index}"
        if not hmac.compare_digest(str(chunk.get("sha256", "")), expected_chunk["sha256"]):
            return False, f"chunk checksum mismatch at index {index}"
    return True, "ok"


def build_transfer_resume_plan(
    envelope: dict[str, Any],
    completed_chunk_indexes: list[int] | tuple[int, ...] | None = None,
) -> dict[str, Any]:
    manifest = envelope.get("chunk_manifest")
    if not isinstance(manifest, dict):
        raise ValueError("resume requires a chunk manifest")
    chunk_count = int(manifest.get("chunk_count", -1))
    if chunk_count < 0:
        raise ValueError("resume requires a valid chunk count")
    completed = sorted({int(index) for index in (completed_chunk_indexes or [])})
    if any(index < 0 or index >= chunk_count for index in completed):
        raise ValueError("completed chunk checkpoint is out of range")
    pending = [index for index in range(chunk_count) if index not in completed]
    return {
        "version": 1,
        "payload_hash": str(envelope.get("payload_hash", "")),
        "chunk_count": chunk_count,
        "completed_chunk_indexes": completed,
        "pending_chunk_indexes": pending,
        "next_chunk_index": pending[0] if pending else None,
        "complete": len(pending) == 0,
    }


def validate_transfer_resume_plan(envelope: dict[str, Any], resume_plan: dict[str, Any]) -> tuple[bool, str]:
    if int(resume_plan.get("version", 0) or 0) != 1:
        return False, "unsupported resume plan version"
    if str(resume_plan.get("payload_hash", "")) != str(envelope.get("payload_hash", "")):
        return False, "resume payload hash mismatch"
    try:
        expected = build_transfer_resume_plan(
            envelope,
            completed_chunk_indexes=list(resume_plan.get("completed_chunk_indexes", [])),
        )
    except (TypeError, ValueError):
        return False, "invalid resume chunk checkpoint"
    for field in ("chunk_count", "completed_chunk_indexes", "pending_chunk_indexes", "next_chunk_index", "complete"):
        if resume_plan.get(field) != expected[field]:
            return False, f"resume {field} mismatch"
    return True, "ok"


def build_transfer_replay_token(envelope: dict[str, Any]) -> str:
    encrypted_payload = str(envelope.get("encrypted_payload", ""))
    nonce_source = encrypted_payload
    try:
        raw = base64.b64decode(encrypted_payload.encode("ascii"))
        blob = json.loads(raw.decode("utf-8"))
        if isinstance(blob, dict) and str(blob.get("nonce_b64", "")).strip():
            nonce_source = str(blob.get("nonce_b64", "")).strip()
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return _json_hash(
        {
            "issuer": str(envelope.get("issuer", "")).strip(),
            "nonce": nonce_source,
        }
    )


def encrypt_json_payload(payload: dict[str, Any], secret_key: str, key_id: str = "") -> str:
    key = _derive_aes256_key(secret_key)
    aes = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = aes.encrypt(nonce, plaintext, associated_data=None)
    blob = {
        "version": 1,
        "alg": "AES-256-GCM",
        "key_id": str(key_id).strip() or "default",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }
    return base64.b64encode(json.dumps(blob, separators=(",", ":")).encode("utf-8")).decode("ascii")


def decrypt_json_payload(encoded_payload: str, secret_key: str | dict[str, str]) -> dict[str, Any]:
    raw = base64.b64decode(str(encoded_payload).encode("ascii"))
    blob = json.loads(raw.decode("utf-8"))
    if not isinstance(blob, dict):
        raise ValueError("encrypted payload blob must be an object")
    if str(blob.get("alg", "")).strip().upper() != "AES-256-GCM":
        raise ValueError("unsupported payload encryption algorithm")

    nonce = base64.b64decode(str(blob.get("nonce_b64", "")).encode("ascii"))
    ciphertext = base64.b64decode(str(blob.get("ciphertext_b64", "")).encode("ascii"))
    key_id = str(blob.get("key_id", "default")).strip() or "default"
    if isinstance(secret_key, dict):
        resolved = str(secret_key.get(key_id, "")).strip() or str(secret_key.get("default", "")).strip()
        if not resolved:
            raise ValueError(f"no key available for key_id='{key_id}'")
        key = _derive_aes256_key(resolved)
    else:
        key = _derive_aes256_key(secret_key)
    aes = AESGCM(key)
    plaintext = aes.decrypt(nonce, ciphertext, associated_data=None)
    payload = json.loads(plaintext.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("decrypted payload must be an object")
    return payload


def build_transfer_envelope(
    *,
    agent_id: str,
    agent_version: str,
    issuer: str,
    target_system_id: str,
    encrypted_payload: str,
    policy_ref: str,
    secret_key: str,
    expires_in_seconds: int = 300,
    envelope_version: int = 1,
    chunk_size: int = 65536,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(seconds=max(1, int(expires_in_seconds)))

    base = {
        "envelope_version": int(envelope_version),
        "agent_id": str(agent_id).strip(),
        "agent_version": str(agent_version).strip(),
        "issuer": str(issuer).strip(),
        "target_system_id": str(target_system_id).strip(),
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "cipher_suite": "AES-256-GCM",
        "encrypted_payload": str(encrypted_payload),
        "policy_ref": str(policy_ref).strip(),
        "chunk_manifest": build_chunk_manifest(str(encrypted_payload), chunk_size=chunk_size),
    }
    base["payload_hash"] = _json_hash({"encrypted_payload": base["encrypted_payload"]})
    message = _json_hash(base).encode("utf-8")
    base["signature"] = hmac.new(str(secret_key).encode("utf-8"), message, hashlib.sha256).hexdigest()
    return base


def validate_transfer_envelope(
    envelope: dict[str, Any],
    secret_key: str,
    replay_tokens: set[str] | None = None,
) -> tuple[bool, str]:
    required = {
        "envelope_version", "agent_id", "agent_version", "issuer", "target_system_id",
        "created_at", "expires_at", "cipher_suite", "encrypted_payload", "payload_hash",
        "signature", "policy_ref",
    }
    missing = [field for field in required if field not in envelope]
    if missing:
        return False, f"missing fields: {', '.join(sorted(missing))}"

    if str(envelope.get("cipher_suite", "")).strip().upper() != "AES-256-GCM":
        return False, "unsupported cipher suite"

    expected_hash = _json_hash({"encrypted_payload": str(envelope.get("encrypted_payload", ""))})
    if str(envelope.get("payload_hash", "")) != expected_hash:
        return False, "payload hash mismatch"

    chunk_manifest = envelope.get("chunk_manifest")
    if chunk_manifest is not None:
        if not isinstance(chunk_manifest, dict):
            return False, "invalid chunk manifest"
        chunks_ok, chunks_reason = validate_chunk_manifest(str(envelope.get("encrypted_payload", "")), chunk_manifest)
        if not chunks_ok:
            return False, chunks_reason

    signing_payload = {k: v for k, v in envelope.items() if k != "signature"}
    expected_sig = hmac.new(
        str(secret_key).encode("utf-8"),
        _json_hash(signing_payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(str(envelope.get("signature", "")), expected_sig):
        return False, "signature mismatch"

    try:
        expires_at = datetime.fromisoformat(str(envelope.get("expires_at", "")))
    except ValueError:
        return False, "invalid expires_at"
    if datetime.now(timezone.utc) >= expires_at.astimezone(timezone.utc):
        return False, "envelope expired"

    if replay_tokens is not None:
        replay_token = build_transfer_replay_token(envelope)
        if replay_token in replay_tokens:
            return False, "replay detected: encrypted payload nonce was already consumed"
        replay_tokens.add(replay_token)

    return True, "ok"


# --- Secure Address and Communication ---
#
# Top-Tier Security Requirements:
# - All address ledgers must be encrypted at rest using AES-256-GCM or equivalent.
# - Encryption keys must be unique per BossGate, never hardcoded, and support rotation (integrate with secure key vaults if possible).
# - All direct communications (encrypted or not) must use TLS 1.3+ with mutual authentication for encrypted comms.
# - Secure address generation: each 7-word address must be generated using cryptographically secure random word selection, ensuring uniqueness and unpredictability.
# - Tamper-evidence: ledgers should be protected with HMAC or digital signatures to detect unauthorized modification.
# - Secure deletion and rotation: support for securely deleting addresses/keys and rotating them as needed (e.g., on agent retirement or compromise).
# - Privacy boundaries: foreign agents/gates only contribute their own address, never their full ledger.
# - All address lists are encrypted at rest and never transmitted in bulk.
#
# TODO: Implement AES-256-GCM encryption/decryption for ledger files.
# TODO: Integrate with a secure key vault for key management and rotation.
# TODO: Use TLS 1.3+ with mutual authentication for all encrypted direct comms.
# TODO: Use os.urandom or secrets module for cryptographically secure address generation.
# TODO: Add HMAC or digital signature to each ledger entry for tamper-evidence.
# TODO: Implement secure deletion (e.g., file shredding) for retired addresses/keys.
#
# Address Ledger Protocol:
# - Every BossGate keeps its own encrypted list of addresses it has traveled to or communicated with.
# - Each home BossForge or Bridgebase has a BossGate with its own unique address.
# - Prime BossGates (at BossForge or Bridgebase) maintain a master list, compiled from all agents/connections made by BossGates created at that location, plus addresses of foreign agents/gates encountered.
# - When connecting to a foreign agent/gate, only the foreign address is added—never the full list of known addresses from the foreign side (privacy boundary).
# - All address lists are encrypted at rest.
# - Foreign agents/gates only contribute their own address, not their full ledger.
# Every BossGate instance must have a secure address in the following format:
#   *word1*word2*word3*word4*word5*word6*word7*
# Each word is an English-language word (e.g., *codemage*star*fox*bravo*king*ice*executioner*).
# The address is derived from the agent connector and serves as the point of origin.
# All direct (encrypted or non-encrypted) communications must include this address for traceability.
# This enables the system to track who sent each message and from where.
#
# Example (to be enforced in future implementations):
#   agent_secure_address = '*codemage*star*fox*bravo*king*ice*executioner*'
#   message = {
#       'from': agent_secure_address,
#       'to': destination_address,
#       'payload': ...
#   }
# Each BossGate instance must have a secure address for encrypted direct communication.
# Two skills gate communication:
#   - 'bossgate_coms_officer': required for encrypted comms (TLS, mutual auth, etc.)
#   - 'bossgate_coms_array': required for non-encrypted comms (plain TCP/UDP)
# Future direct agent-to-agent or agent-to-forge communication must check these skills.
#
# Example usage (to be implemented):
#   if 'bossgate_coms_officer' in agent_skills:
#       # Allow encrypted comms
#   elif 'bossgate_coms_array' in agent_skills:
#       # Allow non-encrypted comms
def scan_rest_endpoints(base_url, agent_skills=None):
    """
    Skill-gated: Requires 'bossgate_scanning' in agent_skills to proceed.
    """
    if agent_skills is not None and "bossgate_scanning" not in agent_skills:
        return {
            "ok": False,
            "reason": "Agent lacks the Bossgate Scanning Skill.",
            "base_url": base_url,
            "endpoints": [],
        }
    base_url = _normalize_url_for_scan(base_url)
    if not base_url:
        return {
            "ok": False,
            "allowed_for_transfer": False,
            "target_type": "unknown",
            "reason": "base_url is required",
            "base_url": "",
            "endpoints": [],
        }

    candidates = [
        '/openapi.json', '/swagger.json', '/swagger/v1/swagger.json', '/api/docs', '/docs/openapi.json'
    ]
    endpoints = []
    metadata = {}

    try:
        _, probe_headers = _http_get_headers(base_url.rstrip('/') + '/health', timeout=2)
        metadata = {
            "server": probe_headers.get("Server", ""),
            "x-powered-by": probe_headers.get("X-Powered-By", ""),
            "x-bossgate-role": probe_headers.get("X-BossGate-Role", ""),
            "x-bossgate-target-type": probe_headers.get("X-BossGate-Target-Type", ""),
        }
    except Exception:
        metadata = {}

    for path in candidates:
        try:
            status, headers, data = _http_get_json(base_url.rstrip('/') + path, timeout=2)
            if status == 200 and 'application/json' in headers.get('Content-Type', ''):
                info = data.get('info') if isinstance(data, dict) else {}
                if isinstance(info, dict):
                    if isinstance(info.get('title'), str):
                        metadata['title'] = info.get('title', '')
                    if isinstance(info.get('description'), str):
                        metadata['description'] = info.get('description', '')
                if 'paths' in data:
                    for ep, methods in data['paths'].items():
                        endpoints.append({'path': ep, 'methods': list(methods.keys())})
                break
        except Exception:
            continue

    if not endpoints:
        common = ['/api', '/health', '/status', '/v1', '/v2']
        for path in common:
            try:
                status, headers = _http_options_headers(base_url.rstrip('/') + path, timeout=2)
                if status < 400:
                    endpoints.append({'path': path, 'methods': headers.get('Allow', '').split(',')})
            except Exception:
                continue

    allowed, target_type = is_valid_transfer_target(metadata)
    if not allowed:
        return {
            "ok": False,
            "allowed_for_transfer": False,
            "target_type": target_type,
            "reason": "Destination rejected: transfer is only allowed to BossGate Connector, A.S.S., BossForgeOS, or bridgebase_alpha targets.",
            "base_url": base_url,
            "endpoints": [],
            "metadata": metadata,
        }

    return {
        "ok": True,
        "allowed_for_transfer": True,
        "target_type": target_type,
        "reason": "Destination validated for transfer.",
        "base_url": base_url,
        "endpoints": endpoints,
        "metadata": metadata,
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='BossGate Connector Prototype')
    parser.add_argument('--scan', metavar='URL', help='Scan a REST app for endpoints (e.g. http://localhost:8000/)')
    parser.add_argument('--beacon', action='store_true', help='Broadcast BossGate beacon on LAN')
    parser.add_argument('--discover', action='store_true', help='Discover BossGate/A.S.S. beacons on LAN')
    parser.add_argument('--node-id', default=socket.gethostname(), help='Node identifier to include in broadcast beacons')
    parser.add_argument('--assistance-only', action='store_true', help='Only return agents requesting assistance')
    args = parser.parse_args()

    if args.beacon:
        print('Broadcasting BossGate beacon...')
        threading.Thread(target=broadcast_beacon, kwargs={"node_id": args.node_id}, daemon=True).start()
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print('Stopped.')
    elif args.discover:
        print('Listening for BossGate/A.S.S. beacons...')
        found = discover_transfer_targets(assistance_only=args.assistance_only)
        print('Found devices:', found)
    elif args.scan:
        print(f'Scanning {args.scan} for REST endpoints...')
        eps = scan_rest_endpoints(args.scan)
        print(json.dumps(eps, indent=2))
    else:
        parser.print_help()
