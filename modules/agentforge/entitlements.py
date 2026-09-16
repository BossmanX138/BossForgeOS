from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentForgeRuntimeContext:
    mode: str
    installation_id: str


class EntitlementProvider(Protocol):
    def resolve(self, context: AgentForgeRuntimeContext) -> dict[str, Any]:
        ...


class StaticEntitlementProvider:
    """Deterministic provider for tests and local development."""

    def __init__(
        self,
        *,
        subscribed: bool,
        capabilities: set[str] | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        self.subscribed = bool(subscribed)
        self.capabilities = set(capabilities or set())
        self.expires_at = expires_at

    def resolve(self, context: AgentForgeRuntimeContext) -> dict[str, Any]:
        return {
            "subject": context.installation_id,
            "product": "agentforge_standalone",
            "subscribed": self.subscribed,
            "verified": True,
            "capabilities": sorted(self.capabilities),
            "expires_at": self.expires_at,
        }


class DenyByDefaultEntitlementProvider:
    def resolve(self, context: AgentForgeRuntimeContext) -> dict[str, Any]:
        return {
            "subject": context.installation_id,
            "product": "agentforge_standalone",
            "subscribed": False,
            "verified": False,
            "capabilities": [],
            "expires_at": None,
        }


def _active_entitlement(decision: dict[str, Any]) -> bool:
    if decision.get("verified") is not True or decision.get("subscribed") is not True:
        return False
    expires_at = decision.get("expires_at")
    if expires_at is None:
        return True
    if not isinstance(expires_at, datetime):
        return False
    normalized = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return normalized > datetime.now(timezone.utc)


def authorize_creation_request(
    *,
    context: AgentForgeRuntimeContext,
    entitlement_provider: EntitlementProvider,
    agent_class: str,
    bossgate_enabled: bool,
    travel_capable: bool,
) -> dict[str, Any]:
    mode = str(context.mode or "").strip().lower()
    normalized_class = str(agent_class or "").strip().lower()
    if mode == "integrated":
        return {
            "agent_class": normalized_class,
            "bossgate_enabled": bool(bossgate_enabled),
            "travel_capable": bool(travel_capable),
            "creation_authority": "bossforgeos",
        }
    if mode != "standalone":
        raise ValueError(f"unsupported AgentForge runtime mode: {mode}")

    entitlement = entitlement_provider.resolve(context)
    subscribed = _active_entitlement(entitlement)
    capabilities = {
        str(item).strip()
        for item in entitlement.get("capabilities", [])
        if str(item).strip()
    }
    if not subscribed:
        if normalized_class == "prime":
            raise PermissionError("Prime agent creation requires an AgentForge subscription")
        if normalized_class not in {"skilled", "normalized"}:
            raise PermissionError("standalone local creation allows Skilled or Normalized agents only")
        return {
            "agent_class": normalized_class,
            "bossgate_enabled": False,
            "travel_capable": False,
            "creation_authority": "standalone_local",
        }

    if normalized_class == "prime" and "agent.create.prime" not in capabilities:
        raise PermissionError("Prime agent creation is not included in this subscription")
    requested_travel = bool(bossgate_enabled) or bool(travel_capable)
    if requested_travel and "agent.create.travel" not in capabilities:
        raise PermissionError("travel-capable creation is not included in this subscription")
    return {
        "agent_class": normalized_class,
        "bossgate_enabled": bool(bossgate_enabled),
        "travel_capable": bool(travel_capable),
        "creation_authority": "standalone_subscribed",
    }
