"""Master agent manifest for one-place visibility and registration bootstrap."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.agent_registry import register_agent


AGENT_MANIFEST: dict[str, dict[str, Any]] = {
    "archivist": {
        "id": "archivist",
        "name": "ArchivistAgent",
        "module": "core.agents.archivist_agent",
        "class": "ArchivistAgent",
        "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
    },
    "codemage": {
        "id": "codemage",
        "name": "CodeMageAgent",
        "module": "core.agents.codemage_agent",
        "class": "CodeMageAgent",
        "description": "Arcane engineer for code and scroll interpretation in BossForge.",
    },
    "devlot": {
        "id": "devlot",
        "name": "DevlotAgent",
        "module": "core.agents.devlot_agent",
        "class": "DevlotAgent",
        "description": "Environment steward and execution utility agent for BossForge tasks.",
    },
    "model_gateway": {
        "id": "model_gateway",
        "name": "ModelGateway",
        "module": "core.agents.model_gateway_agent",
        "class": "ModelGateway",
        "description": "Model endpoint router and cross-node orchestration gateway.",
    },
    "runeforge": {
        "id": "runeforge",
        "name": "RuneforgeAgent",
        "module": "core.agents.runeforge_agent",
        "class": "RuneforgeAgent",
        "description": "First mind of the forge and runtime infrastructure steward.",
    },
    "security_sentinel": {
        "id": "security_sentinel",
        "name": "SecuritySentinelAgent",
        "module": "core.security.security_sentinel_agent",
        "class": "SecuritySentinelAgent",
        "description": "Security policy, vault, and workspace leak sentinel.",
    },
}


def get_master_agent_manifest() -> dict[str, dict[str, Any]]:
    """Return a defensive copy of the canonical agent manifest."""
    return deepcopy(AGENT_MANIFEST)


def bootstrap_master_agent_registry() -> dict[str, dict[str, Any]]:
    """Register all manifest entries into the runtime registry and return the manifest."""
    manifest = get_master_agent_manifest()
    for agent_id, profile in manifest.items():
        register_agent(agent_id, profile)
    return manifest
