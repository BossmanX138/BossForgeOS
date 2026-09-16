from __future__ import annotations

from copy import deepcopy
from typing import Any


CAPSULE_SCHEMA_VERSION = "1.0"
DEFAULT_RARITY = "common"
DEFAULT_AVAILABILITY = "available"
CAPSULE_VAULT_NAMES = (
    "identity",
    "runner",
    "model",
    "memory",
    "capability",
    "dream",
    "bossgate",
)
CAPSULE_LIFECYCLE_STATES = (
    "sealed",
    "installed",
    "waking",
    "idle",
    "active",
    "travel_pending",
    "traveling",
    "dream_eligible",
    "dreaming",
    "dream_validating",
    "rollback",
    "offline",
    "dead",
    "retired",
)
_LIFECYCLE_TRANSITIONS = {
    "sealed": {"installed"},
    "installed": {"waking", "offline"},
    "waking": {"idle", "offline"},
    "idle": {"active", "dream_eligible", "travel_pending", "offline", "dead", "retired"},
    "active": {"idle", "offline", "dead"},
    "travel_pending": {"traveling", "idle", "offline"},
    "traveling": {"installed", "offline"},
    "dream_eligible": {"dreaming", "idle", "offline"},
    "dreaming": {"dream_validating", "rollback", "offline"},
    "dream_validating": {"idle", "rollback", "offline"},
    "rollback": {"idle", "offline"},
    "offline": {"waking", "dead", "retired"},
    "dead": {"retired"},
    "retired": set(),
}
_SEALED_PROFILE_VIEW_FIELDS = {
    "secure_address",
    "gate_file",
    "runtime_lineage",
    "capsule",
    "private_model",
    "private_model_package",
    "memory_vault",
    "capability_vault",
    "dream_vault",
    "bossgate_vault",
}


def _text(value: Any, default: str = "") -> str:
    return str(value or "").strip() or default


def normalize_rarity(value: Any) -> str:
    return _text(value, DEFAULT_RARITY).lower()


def normalize_availability(value: Any) -> str:
    return _text(value, DEFAULT_AVAILABILITY).lower()


def normalize_lifecycle_state(value: Any) -> str:
    state = _text(value, "sealed").lower()
    if state not in CAPSULE_LIFECYCLE_STATES:
        raise ValueError(f"invalid capsule lifecycle state: {state}")
    return state


def build_public_identity_card(profile: dict[str, Any]) -> dict[str, str]:
    public_id = _text(profile.get("public_id"), _text(profile.get("id")))
    return {
        "name": _text(profile.get("name")),
        "public_id": public_id,
        "agent_class": _text(profile.get("agent_class"), "normalized").lower(),
        "agent_type": _text(profile.get("agent_type"), "worker").lower(),
        "rank": _text(profile.get("rank"), "cadet").lower(),
        "rarity": normalize_rarity(profile.get("rarity")),
        "availability": normalize_availability(profile.get("availability")),
    }


def build_runtime_lineage(profile: dict[str, Any]) -> dict[str, Any]:
    raw = profile.get("runtime_lineage")
    lineage = dict(raw) if isinstance(raw, dict) else {}
    agent_id = _text(profile.get("id")).lower()
    default_ancestor = "" if agent_id == "runeforge" else "runeforge"
    return {
        "ancestor_id": _text(lineage.get("ancestor_id"), default_ancestor).lower(),
        "gifted_template_version": _text(lineage.get("gifted_template_version"), "gifted-runtime-v1"),
        "sealed": True,
    }


def build_capsule_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    vault_refs = profile.get("vault_refs")
    refs = dict(vault_refs) if isinstance(vault_refs, dict) else {}
    runtime = profile.get("runtime")
    runtime_data = runtime if isinstance(runtime, dict) else {}
    private_model = runtime_data.get("private_model_package")
    if isinstance(private_model, dict):
        refs["model"] = _text(private_model.get("ciphertext_ref"))
    private_memory = runtime_data.get("private_memory_vault")
    if isinstance(private_memory, dict):
        refs["memory"] = _text(private_memory.get("ciphertext_ref"))
    return {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "agent_id": _text(profile.get("id") or profile.get("name")).lower(),
        "public_identity_card": build_public_identity_card(profile),
        "runtime_lineage": build_runtime_lineage(profile),
        "lifecycle_state": normalize_lifecycle_state(profile.get("lifecycle_state")),
        "vaults": {
            name: {"encrypted": True, "ciphertext_ref": _text(refs.get(name))}
            for name in CAPSULE_VAULT_NAMES
        },
    }


def validate_capsule_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("capsule manifest must be an object")
    if _text(manifest.get("schema_version")) != CAPSULE_SCHEMA_VERSION:
        raise ValueError(f"capsule schema_version must be {CAPSULE_SCHEMA_VERSION}")
    if not _text(manifest.get("agent_id")):
        raise ValueError("capsule agent_id is required")
    card = manifest.get("public_identity_card")
    if not isinstance(card, dict) or set(card) != {
        "name",
        "public_id",
        "agent_class",
        "agent_type",
        "rank",
        "rarity",
        "availability",
    }:
        raise ValueError("capsule public_identity_card must use the sparse public contract")
    lineage = manifest.get("runtime_lineage")
    if not isinstance(lineage, dict) or lineage.get("sealed") is not True:
        raise ValueError("capsule runtime_lineage must be sealed")
    normalize_lifecycle_state(manifest.get("lifecycle_state"))
    vaults = manifest.get("vaults")
    if not isinstance(vaults, dict) or set(vaults) != set(CAPSULE_VAULT_NAMES):
        raise ValueError("capsule vaults must define the complete encrypted vault layout")
    for name in CAPSULE_VAULT_NAMES:
        vault = vaults.get(name)
        if not isinstance(vault, dict) or vault.get("encrypted") is not True:
            raise ValueError(f"capsule vault '{name}' must be encrypted")
        if not isinstance(vault.get("ciphertext_ref"), str):
            raise ValueError(f"capsule vault '{name}' ciphertext_ref must be a string")


def transition_lifecycle(current: Any, target: Any) -> str:
    current_state = normalize_lifecycle_state(current)
    target_state = normalize_lifecycle_state(target)
    if target_state not in _LIFECYCLE_TRANSITIONS[current_state]:
        raise ValueError(f"invalid capsule lifecycle transition: {current_state} -> {target_state}")
    return target_state


def assert_rarity_unchanged(previous: dict[str, Any], candidate: dict[str, Any]) -> None:
    if normalize_rarity(previous.get("rarity")) != normalize_rarity(candidate.get("rarity")):
        raise ValueError("agent rarity is immutable after creation")


def build_authenticated_profile_view(profile: dict[str, Any]) -> dict[str, Any]:
    view = {
        key: deepcopy(value)
        for key, value in profile.items()
        if key not in _SEALED_PROFILE_VIEW_FIELDS
    }
    runtime = view.get("runtime")
    if isinstance(runtime, dict):
        runtime.pop("private_memory_vault", None)
        runtime.pop("private_model_package", None)
    runner_bootstrap = view.get("runner_bootstrap")
    if isinstance(runner_bootstrap, dict):
        runner_bootstrap.pop("private_memory_vault", None)
        runner_bootstrap.pop("private_model_package", None)
    return view
