from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.schemas.agent_schema import infer_incident_domains, rank_agents_for_incident

def _gateway() -> Any:
    from core.agents.model_gateway_agent import ModelGatewayAgent

    return ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)


def discover_travel_targets(
    timeout: int = 5,
    assistance_only: bool = False,
    operator_id: str = "",
    scope_id: str = "",
    actor_type: str = "human",
) -> dict[str, Any]:
    gateway = _gateway()
    return gateway.discover_travel_targets(
        timeout=timeout,
        assistance_only=assistance_only,
        operator_id=operator_id,
        scope_id=scope_id,
        actor_type=actor_type,
    )


def validate_transfer_target(
    destination: str,
    operator_id: str = "",
    scope_id: str = "",
    actor_type: str = "human",
) -> dict[str, Any]:
    gateway = _gateway()
    return gateway.validate_transfer_target(
        destination=str(destination or "").strip(),
        operator_id=operator_id,
        scope_id=scope_id,
        actor_type=actor_type,
    )


def set_agent_assistance_request(name: str, requested: bool = True, reason: str = "") -> dict[str, Any]:
    gateway = _gateway()
    return gateway.set_agent_assistance_request(
        name=str(name or "").strip(),
        requested=bool(requested),
        reason=str(reason or "").strip(),
    )


def list_assistance_requests() -> dict[str, Any]:
    gateway = _gateway()
    return gateway.list_assistance_requests()


def list_owned_agent_locations(refresh: bool = False) -> dict[str, Any]:
    gateway = _gateway()
    return gateway.list_owned_agent_locations(refresh=bool(refresh))


def invoke_endpoint(
    endpoint: str,
    prompt: str,
    system: str = "You are BossForgeOS assistant.",
    temperature: float = 0.2,
    max_tokens: int = 900,
) -> dict[str, Any]:
    gateway = _gateway()
    return gateway.invoke_endpoint(
        str(endpoint or "").strip(),
        str(prompt or "").strip(),
        str(system or "You are BossForgeOS assistant."),
        float(temperature),
        int(max_tokens),
    )


def list_endpoints_from_state(state_path: str) -> dict[str, Any]:
    path = Path(state_path)
    if not path.exists():
        return {"endpoints": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"endpoints": {}}
    if not isinstance(data, dict):
        return {"endpoints": {}}
    return {"endpoints": data}


def list_agent_profiles() -> dict[str, Any]:
    return _gateway().list_agent_profiles()


def create_agent_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return _gateway().create_agent_profile(payload)


def triage_agent_candidates(incident: dict[str, Any], weights: dict[str, Any] | None = None) -> dict[str, Any]:
    profiles = _gateway().list_agent_profiles()
    candidates = []
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        item = dict(profile)
        item.setdefault("id", str(name).strip().lower())
        item.setdefault("name", str(name).strip().lower())
        candidates.append(item)
    ranked = rank_agents_for_incident(incident=incident, agent_profiles=candidates, weights=weights)
    return {
        "ok": True,
        "incident_inference": infer_incident_domains(incident),
        "ranked_candidates": ranked,
        "candidate_count": len(candidates),
    }


def delete_agent_profile(name: str) -> dict[str, Any]:
    return _gateway().delete_agent_profile(str(name or "").strip())


def run_agent_profile(name: str, task: str, endpoint: str, memory_context: dict[str, Any] | None = None) -> dict[str, Any]:
    return _gateway().run_agent_profile(
        str(name or "").strip(),
        str(task or "").strip(),
        str(endpoint or "").strip(),
        memory_context=memory_context or {},
    )


def recall_agent_memory(name: str, limit: int = 25) -> dict[str, Any]:
    return _gateway().recall_agent_memory(name=str(name or "").strip(), limit=int(limit))
