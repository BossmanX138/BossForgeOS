from __future__ import annotations

from typing import Any


def _gateway() -> Any:
    from core.agents.model_gateway_agent import ModelGatewayAgent

    return ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)


def discover_travel_targets(timeout: int = 5, assistance_only: bool = False) -> dict[str, Any]:
    gateway = _gateway()
    return gateway.discover_travel_targets(timeout=timeout, assistance_only=assistance_only)


def validate_transfer_target(destination: str) -> dict[str, Any]:
    gateway = _gateway()
    return gateway.validate_transfer_target(destination=str(destination or "").strip())


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

