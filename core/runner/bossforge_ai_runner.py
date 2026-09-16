from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from typing import Any

from core.memory_vault import validate_private_memory_descriptor
from core.model_vault import validate_private_model_descriptor


RUNNER_CONTRACT_VERSION = "1.0"
GIFTED_TEMPLATE_VERSION = "gifted-runtime-v1"
RUNEFORGE_AGENT_ID = "runeforge"
SIGNATURE_SCHEME = "bossforge-runner-template-dev-integrity-v1"
# Stage 2 uses deterministic integrity metadata only; this is not a production trust root.
_SIGNING_KEY = b"bossforge-ai-runner-stage2-dev-signing-key"


def _text(value: Any, default: str = "") -> str:
    return str(value or "").strip() or default


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_payload(payload: dict[str, Any]) -> str:
    return hmac.new(_SIGNING_KEY, _canonical_payload(payload), hashlib.sha256).hexdigest()


def build_neutral_runner_template() -> dict[str, Any]:
    return {
        "template_id": "bossforge-ai-runner-neutral",
        "version": GIFTED_TEMPLATE_VERSION,
        "contract_version": RUNNER_CONTRACT_VERSION,
        "signature_scheme": SIGNATURE_SCHEME,
        "gifted_by": RUNEFORGE_AGENT_ID,
        "runner_kind": "bossforge_ai_runner",
        "runtime_requirements": {
            "python": "3.11+",
            "api_style": "openai-compatible",
            "supports_local_model": True,
            "supports_tools": True,
            "supports_state_machine": True,
        },
        "bootstrap_contracts": {
            "wake": "bossforge-ai-runner-wake-v1",
            "install": "bossforge-ai-runner-install-v1",
            "attestation": "bossforge-ai-runner-attestation-v1",
        },
        "sealed_capabilities": [
            "runner_config",
            "model_loader",
            "tool_mediation",
            "state_machine",
            "wake_controls",
        ],
    }


def build_signed_gifted_template() -> dict[str, Any]:
    template = build_neutral_runner_template()
    template["signature"] = _sign_payload(template)
    return template


def verify_signed_template(template: dict[str, Any]) -> bool:
    if not isinstance(template, dict):
        return False
    signature = _text(template.get("signature"))
    if not signature:
        return False
    expected = _sign_payload(template)
    return hmac.compare_digest(signature, expected)


def build_runeforge_origin_manifest() -> dict[str, Any]:
    template = build_signed_gifted_template()
    return {
        "agent_id": RUNEFORGE_AGENT_ID,
        "runner_role": "personalized_origin",
        "runner_contract_version": RUNNER_CONTRACT_VERSION,
        "independent_runner_version": "runeforge-personalized-v1",
        "source_template": {
            "template_id": template["template_id"],
            "version": template["version"],
            "ancestor_id": "",
            "signature": template["signature"],
        },
        "detached_after_creation": True,
        "depends_on_runeforge_online": False,
        "sealed": True,
    }


def build_agent_runner_manifest(
    agent_id: str, template: dict[str, Any] | None = None
) -> dict[str, Any]:
    normalized_id = _text(agent_id).lower()
    if not normalized_id:
        raise ValueError("agent_id is required for runner manifest")
    signed_template = deepcopy(template) if isinstance(template, dict) else build_signed_gifted_template()
    if not verify_signed_template(signed_template):
        raise ValueError("gifted runner template signature is invalid")
    if normalized_id == RUNEFORGE_AGENT_ID:
        return build_runeforge_origin_manifest()
    return {
        "agent_id": normalized_id,
        "runner_role": "descendant",
        "runner_contract_version": RUNNER_CONTRACT_VERSION,
        "independent_runner_version": f"{normalized_id}-runner-v1",
        "source_template": {
            "template_id": signed_template["template_id"],
            "version": signed_template["version"],
            "ancestor_id": RUNEFORGE_AGENT_ID,
            "signature": signed_template["signature"],
        },
        "detached_after_creation": True,
        "depends_on_runeforge_online": False,
        "sealed": True,
    }


def validate_agent_runner_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("runner manifest must be an object")
    raw_agent_id = manifest.get("agent_id")
    agent_id = _text(raw_agent_id)
    if not agent_id:
        raise ValueError("runner manifest agent_id is required")
    if raw_agent_id != agent_id.lower():
        raise ValueError("runner manifest agent_id must be normalized lowercase")
    if manifest.get("sealed") is not True:
        raise ValueError("runner manifest must be sealed")
    if manifest.get("depends_on_runeforge_online") is not False:
        raise ValueError("runner manifest must not depend on RuneForge being online")
    if manifest.get("detached_after_creation") is not True:
        raise ValueError("runner manifest must be detached after creation")
    if manifest.get("runner_contract_version") != RUNNER_CONTRACT_VERSION:
        raise ValueError("runner manifest contract version is invalid")
    if not _text(manifest.get("independent_runner_version")):
        raise ValueError("runner manifest independent runner version is required")
    role = _text(manifest.get("runner_role")).lower()
    if role not in {"personalized_origin", "descendant"}:
        raise ValueError("runner_role must be personalized_origin or descendant")
    if role == "personalized_origin" and agent_id != RUNEFORGE_AGENT_ID:
        raise ValueError("only RuneForge may declare a personalized origin runner")
    if role == "descendant" and agent_id == RUNEFORGE_AGENT_ID:
        raise ValueError("RuneForge must declare a personalized origin runner")
    expected_independent_version = (
        "runeforge-personalized-v1"
        if role == "personalized_origin"
        else f"{agent_id}-runner-v1"
    )
    if manifest.get("independent_runner_version") != expected_independent_version:
        raise ValueError("runner manifest independent runner version is invalid")
    source = manifest.get("source_template")
    if not isinstance(source, dict):
        raise ValueError("runner manifest source_template is required")
    if source.get("template_id") != "bossforge-ai-runner-neutral":
        raise ValueError("runner manifest source_template template_id is invalid")
    if source.get("version") != GIFTED_TEMPLATE_VERSION:
        raise ValueError("runner manifest source_template version is invalid")
    expected_signature = build_signed_gifted_template()["signature"]
    if source.get("signature") != expected_signature:
        raise ValueError("runner manifest source_template signature is invalid")
    if role == "personalized_origin" and source.get("ancestor_id") != "":
        raise ValueError("RuneForge origin manifest must not declare an ancestor")
    if role == "descendant" and source.get("ancestor_id") != RUNEFORGE_AGENT_ID:
        raise ValueError("descendant runner manifests must record RuneForge ancestry")


def build_runner_bootstrap(
    agent_id: str,
    manifest: dict[str, Any],
    private_model_package: dict[str, Any] | None = None,
    private_memory_vault: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_agent_runner_manifest(manifest)
    normalized_id = _text(agent_id).lower()
    if manifest["agent_id"] != normalized_id:
        raise ValueError("runner bootstrap agent_id must match manifest")
    bootstrap = {
        "agent_id": normalized_id,
        "wake_contract": "bossforge-ai-runner-wake-v1",
        "install_contract": "bossforge-ai-runner-install-v1",
        "attestation_contract": "bossforge-ai-runner-attestation-v1",
        "runner_manifest": deepcopy(manifest),
        "vault_bindings": {
            "runner": "capsule.vaults.runner",
            "model": "capsule.vaults.model",
            "memory": "capsule.vaults.memory",
            "capability": "capsule.vaults.capability",
        },
    }
    if private_model_package is not None:
        validate_private_model_descriptor(
            private_model_package,
            expected_agent_id=normalized_id,
        )
        bootstrap["private_model_package"] = deepcopy(private_model_package)
    if private_memory_vault is not None:
        validate_private_memory_descriptor(
            private_memory_vault,
            expected_agent_id=normalized_id,
        )
        bootstrap["private_memory_vault"] = deepcopy(private_memory_vault)
    return bootstrap


def validate_runner_bootstrap(bootstrap: dict[str, Any]) -> None:
    if not isinstance(bootstrap, dict):
        raise ValueError("runner bootstrap must be an object")
    raw_agent_id = bootstrap.get("agent_id")
    agent_id = _text(raw_agent_id)
    if not agent_id:
        raise ValueError("runner bootstrap agent_id is required")
    if raw_agent_id != agent_id.lower():
        raise ValueError("runner bootstrap agent_id must be normalized lowercase")
    manifest = bootstrap.get("runner_manifest")
    validate_agent_runner_manifest(manifest)
    if manifest["agent_id"] != agent_id:
        raise ValueError("runner bootstrap agent_id must match manifest")
    if bootstrap.get("wake_contract") != "bossforge-ai-runner-wake-v1":
        raise ValueError("runner bootstrap wake contract is invalid")
    if bootstrap.get("install_contract") != "bossforge-ai-runner-install-v1":
        raise ValueError("runner bootstrap install contract is invalid")
    if bootstrap.get("attestation_contract") != "bossforge-ai-runner-attestation-v1":
        raise ValueError("runner bootstrap attestation contract is invalid")
    vault_bindings = bootstrap.get("vault_bindings")
    if not isinstance(vault_bindings, dict):
        raise ValueError("runner bootstrap vault_bindings are required")
    for key in ("runner", "model", "memory", "capability"):
        if not _text(vault_bindings.get(key)):
            raise ValueError(f"runner bootstrap vault binding is required: {key}")
    private_model_package = bootstrap.get("private_model_package")
    if private_model_package is not None:
        validate_private_model_descriptor(
            private_model_package,
            expected_agent_id=agent_id,
        )
    private_memory_vault = bootstrap.get("private_memory_vault")
    if private_memory_vault is not None:
        validate_private_memory_descriptor(
            private_memory_vault,
            expected_agent_id=agent_id,
        )
