from __future__ import annotations

from typing import Any

from core.schemas.agent_capsule import build_authenticated_profile_view, build_public_identity_card
from modules.agentforge.entitlements import (
    AgentForgeRuntimeContext,
    DenyByDefaultEntitlementProvider,
    EntitlementProvider,
    authorize_creation_request,
)

TRUSTED_VIEWER_CHANNELS = {
    "bossforgeos": True,
    "agentforge_standalone": True,
    "bridgebase_alpha": False,
}


def _gateway() -> Any:
    from core.agents.model_gateway_agent import ModelGatewayAgent

    return ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)


def _entitlement_provider() -> EntitlementProvider:
    return DenyByDefaultEntitlementProvider()


def list_agent_profiles() -> dict[str, Any]:
    gateway = _gateway()
    return {"agents": gateway.list_agent_profiles()}


def _sealed_summary(name: str, profile: dict[str, Any]) -> dict[str, Any]:
    model_card = profile.get("agent_card") if isinstance(profile.get("agent_card"), dict) else build_public_identity_card(profile)
    return {
        "ok": True,
        "agent": name,
        "disclosure_posture": str(profile.get("disclosure_posture", "hidden")).strip().lower() or "hidden",
        "sealed": True,
        "view_policy": "model_card_only_outside_origin_forge",
        "message": "Model card only. Full profile view is restricted to the forge of creation.",
        "full_view_available_at_origin_forge": True,
        "public_identity_card": build_public_identity_card(profile),
        "model_card": model_card,
    }


def view_agent_profile(name: str, viewer_id: str = "", viewer_channel: str = "") -> dict[str, Any]:
    key = str(name or "").strip().lower()
    gateway = _gateway()
    profiles = gateway.list_agent_profiles()
    profile = profiles.get(key)
    if not isinstance(profile, dict):
        return {"ok": False, "message": f"agent not found: {key}"}
    summary = _sealed_summary(key, profile)
    posture = str(profile.get("disclosure_posture", "hidden")).strip().lower() or "hidden"
    if posture != "non_hidden":
        return summary
    channel = str(viewer_channel or "").strip().lower()
    created_by_node = str(profile.get("created_by_node", "")).strip()
    forge_of_creation = created_by_node and created_by_node == getattr(gateway, "node_id", "")
    if not str(viewer_id or "").strip() or not TRUSTED_VIEWER_CHANNELS.get(channel, False) or not forge_of_creation:
        return summary
    return {
        "ok": True,
        "agent": key,
        "disclosure_posture": posture,
        "sealed": False,
        "profile": build_authenticated_profile_view(profile),
    }


def set_agent_disclosure_posture(name: str, posture: str) -> dict[str, Any]:
    return _gateway().set_agent_disclosure_posture(str(name or "").strip(), str(posture or "").strip())


def create_agent_profile(
    payload: dict[str, Any],
    *,
    runtime_context: AgentForgeRuntimeContext | None = None,
    entitlement_provider: EntitlementProvider | None = None,
) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    endpoint = str(payload.get("endpoint", "")).strip()
    system = str(payload.get("system", "You are a helpful specialist agent."))
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 900))
    agent_class = str(payload.get("agent_class", "prime")).strip().lower()
    has_llm_raw = payload.get("has_llm")
    has_llm = bool(has_llm_raw) if isinstance(has_llm_raw, bool) else None
    bossgate_enabled_raw = payload.get("bossgate_enabled")
    bossgate_enabled = True if bossgate_enabled_raw is None else bool(bossgate_enabled_raw)
    encrypt_profile_raw = payload.get("encrypt_profile")
    encrypt_profile = True if encrypt_profile_raw is None else bool(encrypt_profile_raw)
    agent_type = str(payload.get("agent_type", "")).strip().lower() or None
    rank = str(payload.get("rank", "")).strip().lower() or None
    skills_raw = payload.get("skills")
    skills = skills_raw if isinstance(skills_raw, list) else None
    sigils_raw = payload.get("sigils")
    sigils = sigils_raw if isinstance(sigils_raw, list) else None
    dispatch_policy_raw = payload.get("dispatch_policy")
    dispatch_policy = dispatch_policy_raw if isinstance(dispatch_policy_raw, dict) else None
    personality_wrapper_raw = payload.get("personality_wrapper")
    personality_wrapper = personality_wrapper_raw if isinstance(personality_wrapper_raw, dict) else None
    system_wrapper_raw = payload.get("system_wrapper")
    system_wrapper = system_wrapper_raw if isinstance(system_wrapper_raw, dict) else None
    instructions_raw = payload.get("instructions")
    instructions = instructions_raw if isinstance(instructions_raw, dict) else None
    state_machine_raw = payload.get("state_machine")
    state_machine = state_machine_raw if isinstance(state_machine_raw, dict) else None
    custom_icon_path = str(payload.get("custom_icon_path", "")).strip() or None
    model_source_path = str(payload.get("model_source_path", "")).strip() or None
    model_base_source_path = str(payload.get("model_base_source_path", "")).strip() or None
    model_runtime_requirements_raw = payload.get("model_runtime_requirements")
    model_runtime_requirements = (
        model_runtime_requirements_raw
        if isinstance(model_runtime_requirements_raw, dict)
        else None
    )
    travel_capable = bool(payload.get("travel_capable", bossgate_enabled))

    trusted_context = runtime_context or AgentForgeRuntimeContext(
        mode="standalone",
        installation_id="local",
    )
    try:
        authorization = authorize_creation_request(
            context=trusted_context,
            entitlement_provider=entitlement_provider or _entitlement_provider(),
            agent_class=agent_class,
            bossgate_enabled=bossgate_enabled,
            travel_capable=travel_capable,
        )
    except (PermissionError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    gateway = _gateway()
    return gateway.create_agent_profile(
        name,
        endpoint,
        system,
        temperature,
        max_tokens,
        agent_class=str(authorization["agent_class"]),
        has_llm=has_llm,
        bossgate_enabled=bool(authorization["bossgate_enabled"]),
        encrypt_profile=encrypt_profile,
        agent_type=agent_type,
        rank=rank,
        skills=skills,
        sigils=sigils,
        dispatch_policy=dispatch_policy,
        personality_wrapper=personality_wrapper,
        system_wrapper=system_wrapper,
        instructions=instructions,
        state_machine=state_machine,
        custom_icon_path=custom_icon_path,
        model_source_path=model_source_path,
        model_base_source_path=model_base_source_path,
        model_runtime_requirements=model_runtime_requirements,
    )
