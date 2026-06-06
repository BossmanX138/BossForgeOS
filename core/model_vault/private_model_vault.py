from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MODEL_VAULT_SCHEMA_VERSION = "1.0"
_WEIGHT_INDEX_NAMES = {
    "model.safetensors.index.json",
    "pytorch_model.bin.index.json",
}


def _resolve_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"model source path escapes root: {candidate}")
    return resolved


def _category(relative_path: str) -> str:
    name = Path(relative_path).name.lower()
    if name.startswith("adapter_"):
        return "adapter"
    if (
        name.endswith((".safetensors", ".bin", ".gguf"))
        or name in _WEIGHT_INDEX_NAMES
    ):
        return "weights"
    if name.startswith(("tokenizer", "vocab", "merges", "special_tokens")):
        return "tokenizer"
    if name == "config.json":
        return "model_config"
    if name == "generation_config.json":
        return "generation_config"
    if name in {"requirements.txt", "runtime_requirements.json"}:
        return "runtime_requirements"
    return "supporting"


def _validate_declared_shards(root: Path, files: list[dict[str, Any]]) -> None:
    for item in files:
        source_relative_path = str(item["source_relative_path"])
        if Path(source_relative_path).name.lower() not in _WEIGHT_INDEX_NAMES:
            continue
        index_path = Path(str(item["source_path"]))
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid model weight index: {source_relative_path}") from exc
        weight_map = payload.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            raise ValueError(f"model weight index has no weight_map: {source_relative_path}")
        for declared in sorted({str(value).strip() for value in weight_map.values()}):
            if not declared:
                raise ValueError(
                    f"model weight index has an empty declared shard: {source_relative_path}"
                )
            candidate = root / declared
            try:
                resolved = _resolve_inside(root, candidate)
            except (FileNotFoundError, OSError, RuntimeError) as exc:
                raise ValueError(f"declared shard is missing: {declared}") from exc
            if not resolved.is_file():
                raise ValueError(f"declared shard is missing: {declared}")


def _inventory_group(root: Path, source_group: str, prefix: str = "") -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_symlink():
            raise ValueError(f"model source links are not allowed: {path}")
        if not path.is_file():
            continue
        resolved = _resolve_inside(root, path)
        source_relative = resolved.relative_to(root).as_posix()
        relative = f"{prefix}/{source_relative}" if prefix else source_relative
        files.append(
            {
                "source_path": str(resolved),
                "source_relative_path": source_relative,
                "relative_path": relative,
                "source_group": source_group,
                "size": resolved.stat().st_size,
                "category": _category(source_relative),
            }
        )
    _validate_declared_shards(root, files)
    return files


def _validate_complete_model(files: list[dict[str, Any]]) -> set[str]:
    present = {str(item["category"]) for item in files}
    for required, message in (
        ("weights", "model weights are required"),
        ("tokenizer", "tokenizer assets are required"),
        ("model_config", "model configuration is required"),
    ):
        if required not in present:
            raise ValueError(message)
    return present


def _resolve_adapter_base(adapter_root: Path, base_source_root: str | Path | None) -> Path:
    candidate = Path(base_source_root) if base_source_root is not None else None
    if candidate is None:
        config_path = adapter_root / "adapter_config.json"
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("adapter base model configuration is invalid") from exc
        declared = str(payload.get("base_model_name_or_path", "")).strip()
        if declared:
            declared_path = Path(declared)
            candidate = declared_path if declared_path.is_absolute() else adapter_root / declared_path
    if candidate is None:
        raise ValueError("adapter base model is required")
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise ValueError(f"adapter base model does not exist: {candidate}") from exc
    if not resolved.is_dir():
        raise ValueError("adapter base model must be a directory")
    return resolved


def inspect_model_source(
    source_root: str | Path,
    base_source_root: str | Path | None = None,
) -> dict[str, object]:
    try:
        root = Path(source_root).resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise ValueError(f"model source does not exist: {source_root}") from exc
    if not root.is_dir():
        raise ValueError("model source must be a directory")

    adapter_only = (
        (root / "adapter_config.json").is_file()
        and (root / "adapter_model.safetensors").is_file()
        and not any((root / name).is_file() for name in _WEIGHT_INDEX_NAMES)
        and not (root / "model.safetensors").is_file()
        and not (root / "pytorch_model.bin").is_file()
    )
    if adapter_only:
        base_root = _resolve_adapter_base(root, base_source_root)
        adapter_files = _inventory_group(root, "adapter", "adapter")
        base_files = _inventory_group(base_root, "base", "base")
        present = _validate_complete_model(base_files)
        present.update(str(item["category"]) for item in adapter_files)
        files = sorted(
            [*adapter_files, *base_files],
            key=lambda item: str(item["relative_path"]),
        )
        source_roots = {"adapter": str(root), "base": str(base_root)}
    else:
        files = _inventory_group(root, "model")
        present = _validate_complete_model(files)
        source_roots = {"model": str(root)}

    return {
        "source_root": str(root),
        "source_roots": source_roots,
        "adapter_only": adapter_only,
        "files": files,
        "present_categories": sorted(present),
        "required_categories": ["model_config", "tokenizer", "weights"],
        "total_size": sum(int(item["size"]) for item in files),
    }


def _normalized_agent_id(value: str) -> str:
    agent_id = str(value or "").strip().lower()
    if (
        not agent_id
        or agent_id in {".", ".."}
        or "/" in agent_id
        or "\\" in agent_id
    ):
        raise ValueError("agent_id must be a normalized path-safe identifier")
    return agent_id


def _aes_key(secret_key: str) -> bytes:
    secret = str(secret_key or "")
    if not secret:
        raise ValueError("private model secret_key is required")
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _chunk_aad(
    *,
    package_id: str,
    owner_agent_id: str,
    relative_path: str,
    chunk_index: int,
    plaintext_size: int,
) -> bytes:
    return _canonical_json(
        {
            "package_id": package_id,
            "owner_agent_id": owner_agent_id,
            "relative_path": relative_path,
            "chunk_index": chunk_index,
            "plaintext_size": plaintext_size,
        }
    )


def _encrypt_json(payload: dict[str, Any], aes: AESGCM) -> dict[str, str | int]:
    nonce = secrets.token_bytes(12)
    ciphertext = aes.encrypt(nonce, _canonical_json(payload), None)
    return {
        "version": 1,
        "alg": "AES-256-GCM",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }


def _decrypt_json(blob: dict[str, Any], aes: AESGCM) -> dict[str, Any]:
    if str(blob.get("alg", "")).upper() != "AES-256-GCM":
        raise ValueError("unsupported private model encryption algorithm")
    try:
        nonce = base64.b64decode(str(blob["nonce_b64"]), validate=True)
        ciphertext = base64.b64decode(str(blob["ciphertext_b64"]), validate=True)
        plaintext = aes.decrypt(nonce, ciphertext, None)
        payload = json.loads(plaintext.decode("utf-8"))
    except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError, InvalidTag) as exc:
        raise ValueError("private model manifest authentication failed") from exc
    if not isinstance(payload, dict):
        raise ValueError("private model manifest must decrypt to an object")
    return payload


def build_private_model_package(
    *,
    agent_id: str,
    source_root: str | Path,
    vault_root: str | Path,
    secret_key: str,
    key_ref: str,
    base_source_root: str | Path | None = None,
    runtime_requirements: dict[str, object] | None = None,
    chunk_size: int = 4 * 1024 * 1024,
) -> dict[str, object]:
    owner_agent_id = _normalized_agent_id(agent_id)
    normalized_key_ref = str(key_ref or "").strip()
    if not normalized_key_ref:
        raise ValueError("private model key_ref is required")
    safe_chunk_size = int(chunk_size)
    if safe_chunk_size <= 0:
        raise ValueError("private model chunk_size must be positive")

    inventory = inspect_model_source(source_root, base_source_root=base_source_root)
    root = Path(vault_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    total_size = int(inventory["total_size"])
    required_bytes = max(total_size * 2, total_size + 16 * 1024 * 1024)
    if shutil.disk_usage(root).free < required_bytes:
        raise ValueError("insufficient disk space for encrypted model package")
    package_id = f"pmv-{secrets.token_hex(16)}"
    staging = root / ".staging" / f"{owner_agent_id}-{package_id}"
    final = root / owner_agent_id / package_id
    if final.exists():
        raise ValueError(f"private model package already exists: {package_id}")

    aes = AESGCM(_aes_key(secret_key))
    manifest_files: list[dict[str, Any]] = []
    activated = False
    try:
        (staging / "chunks").mkdir(parents=True, exist_ok=False)
        for file_item in inventory["files"]:
            relative_path = str(file_item["relative_path"])
            file_id = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
            chunk_dir = staging / "chunks" / file_id
            chunk_dir.mkdir(parents=True)
            plaintext_hasher = hashlib.sha256()
            chunk_records: list[dict[str, Any]] = []
            with Path(str(file_item["source_path"])).open("rb") as source:
                chunk_index = 0
                while True:
                    plaintext = source.read(safe_chunk_size)
                    if not plaintext:
                        break
                    plaintext_hasher.update(plaintext)
                    nonce = secrets.token_bytes(12)
                    aad = _chunk_aad(
                        package_id=package_id,
                        owner_agent_id=owner_agent_id,
                        relative_path=relative_path,
                        chunk_index=chunk_index,
                        plaintext_size=len(plaintext),
                    )
                    ciphertext = aes.encrypt(nonce, plaintext, aad)
                    chunk_blob = {
                        "version": 1,
                        "alg": "AES-256-GCM",
                        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
                    }
                    chunk_relpath = f"chunks/{file_id}/{chunk_index:06d}.chunk"
                    (staging / chunk_relpath).write_text(
                        json.dumps(chunk_blob, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    chunk_records.append(
                        {
                            "index": chunk_index,
                            "storage_path": chunk_relpath,
                            "plaintext_size": len(plaintext),
                            "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
                            "ciphertext_size": len(ciphertext),
                            "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
                        }
                    )
                    chunk_index += 1
            manifest_files.append(
                {
                    "relative_path": relative_path,
                    "source_group": str(file_item["source_group"]),
                    "category": str(file_item["category"]),
                    "size": int(file_item["size"]),
                    "sha256": plaintext_hasher.hexdigest(),
                    "chunks": chunk_records,
                }
            )

        manifest = {
            "schema_version": MODEL_VAULT_SCHEMA_VERSION,
            "package_id": package_id,
            "owner_agent_id": owner_agent_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "key_ref": normalized_key_ref,
            "source_roots": inventory["source_roots"],
            "adapter_only": bool(inventory["adapter_only"]),
            "present_categories": inventory["present_categories"],
            "required_categories": inventory["required_categories"],
            "runtime_requirements": dict(runtime_requirements or {}),
            "files": manifest_files,
            "genesis_checkpoint": {
                "kind": "package_attestation",
                "package_id": package_id,
            },
        }
        encrypted_manifest = _encrypt_json(manifest, aes)
        manifest_bytes = _canonical_json(encrypted_manifest)
        (staging / "package.manifest.enc").write_bytes(manifest_bytes)
        attestation = {
            "schema_version": MODEL_VAULT_SCHEMA_VERSION,
            "package_id": package_id,
            "owner_agent_id": owner_agent_id,
            "alg": "AES-256-GCM",
            "key_ref": normalized_key_ref,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "verified": False,
        }
        (staging / "package.attestation.json").write_text(
            json.dumps(attestation, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        verify_private_model_package(staging, secret_key)
        attestation["verified"] = True
        (staging / "package.attestation.json").write_text(
            json.dumps(attestation, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(final)
        activated = True
        return {
            "schema_version": MODEL_VAULT_SCHEMA_VERSION,
            "package_id": package_id,
            "owner_agent_id": owner_agent_id,
            "package_path": str(final),
            "ciphertext_ref": str(final),
            "attestation_sha256": hashlib.sha256(
                (final / "package.attestation.json").read_bytes()
            ).hexdigest(),
            "key_ref": normalized_key_ref,
            "verified": True,
        }
    finally:
        if not activated and staging.exists():
            shutil.rmtree(staging)


def verify_private_model_package(
    package_root: str | Path,
    secret_key: str,
) -> dict[str, Any]:
    root = Path(package_root).resolve(strict=True)
    try:
        attestation = json.loads(
            (root / "package.attestation.json").read_text(encoding="utf-8")
        )
        manifest_bytes = (root / "package.manifest.enc").read_bytes()
        encrypted_manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("private model package metadata is invalid") from exc
    expected_manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if str(attestation.get("manifest_sha256", "")) != expected_manifest_hash:
        raise ValueError("private model encrypted manifest digest mismatch")

    aes = AESGCM(_aes_key(secret_key))
    manifest = _decrypt_json(encrypted_manifest, aes)
    if manifest.get("package_id") != attestation.get("package_id"):
        raise ValueError("private model package_id mismatch")
    if manifest.get("owner_agent_id") != attestation.get("owner_agent_id"):
        raise ValueError("private model owner mismatch")

    for file_item in manifest.get("files", []):
        relative_path = str(file_item["relative_path"])
        file_hasher = hashlib.sha256()
        reconstructed_size = 0
        for chunk in file_item.get("chunks", []):
            chunk_path = root / str(chunk["storage_path"])
            try:
                blob = json.loads(chunk_path.read_text(encoding="utf-8"))
                nonce = base64.b64decode(str(blob["nonce_b64"]), validate=True)
                ciphertext = base64.b64decode(str(blob["ciphertext_b64"]), validate=True)
            except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("private model ciphertext chunk is invalid") from exc
            if hashlib.sha256(ciphertext).hexdigest() != str(chunk["ciphertext_sha256"]):
                raise ValueError("private model ciphertext digest mismatch")
            aad = _chunk_aad(
                package_id=str(manifest["package_id"]),
                owner_agent_id=str(manifest["owner_agent_id"]),
                relative_path=relative_path,
                chunk_index=int(chunk["index"]),
                plaintext_size=int(chunk["plaintext_size"]),
            )
            try:
                plaintext = aes.decrypt(nonce, ciphertext, aad)
            except InvalidTag as exc:
                raise ValueError("private model chunk authentication failed") from exc
            if hashlib.sha256(plaintext).hexdigest() != str(chunk["plaintext_sha256"]):
                raise ValueError("private model plaintext digest mismatch")
            reconstructed_size += len(plaintext)
            file_hasher.update(plaintext)
        if reconstructed_size != int(file_item["size"]):
            raise ValueError("private model reconstructed file size mismatch")
        if file_hasher.hexdigest() != str(file_item["sha256"]):
            raise ValueError("private model reconstructed file digest mismatch")
    return manifest


def validate_private_model_descriptor(
    descriptor: dict[str, Any],
    *,
    expected_agent_id: str,
    vault_root: str | Path | None = None,
) -> None:
    if not isinstance(descriptor, dict):
        raise ValueError("private model descriptor must be an object")
    owner = _normalized_agent_id(str(descriptor.get("owner_agent_id", "")))
    expected = _normalized_agent_id(expected_agent_id)
    if owner != expected:
        raise ValueError("private model descriptor owner does not match agent")
    if descriptor.get("schema_version") != MODEL_VAULT_SCHEMA_VERSION:
        raise ValueError("private model descriptor schema version is invalid")
    package_id = str(descriptor.get("package_id", "")).strip()
    if not package_id:
        raise ValueError("private model descriptor package_id is required")
    if descriptor.get("verified") is not True:
        raise ValueError("private model descriptor must be verified")
    if not str(descriptor.get("key_ref", "")).strip():
        raise ValueError("private model descriptor key_ref is required")
    if not str(descriptor.get("ciphertext_ref", "")).strip():
        raise ValueError("private model descriptor ciphertext_ref is required")
    attestation_sha256 = str(descriptor.get("attestation_sha256", "")).strip()
    if len(attestation_sha256) != 64:
        raise ValueError("private model descriptor attestation digest is invalid")

    if vault_root is None:
        return
    root = Path(vault_root).resolve()
    owner_root = (root / owner).resolve()
    package_path = Path(str(descriptor.get("package_path", ""))).resolve(strict=True)
    if package_path.parent != owner_root:
        raise ValueError("private model descriptor package path violates owner isolation")
    if package_path.name != package_id:
        raise ValueError("private model descriptor package path does not match package_id")
    attestation_path = package_path / "package.attestation.json"
    try:
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("private model package attestation is invalid") from exc
    if attestation.get("owner_agent_id") != owner:
        raise ValueError("private model package attestation owner mismatch")
    if attestation.get("package_id") != package_id:
        raise ValueError("private model package attestation package_id mismatch")
