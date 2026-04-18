"""
Central Agent Registry for BossForgeOS
Provides a singleton registry for agent registration, discovery, and metadata lookup.
All agents should register themselves here at startup for unified orchestration.
"""
import threading
from typing import Any, Dict, Optional

from core.schemas import normalize_agent_profile, to_agent_card, validate_agent_profile

class AgentRegistry:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._agents = {}
        return cls._instance

    def register_agent(self, agent_id: str, profile: Optional[Dict[str, Any]] = None) -> None:
        """Register an agent with its profile (id, name, description, etc)."""
        if not agent_id:
            raise ValueError("agent_id is required")
        normalized = normalize_agent_profile(agent_id=agent_id, profile=profile)
        validate_agent_profile(normalized)
        self._agents[normalized["id"]] = normalized

    def unregister_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def get_agent_profile(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._agents)

    def get_agent_card(self, agent_id: str) -> Optional[Dict[str, Any]]:
        profile = self._agents.get(agent_id)
        if not isinstance(profile, dict):
            return None
        return to_agent_card(profile)

    def list_agent_cards(self) -> Dict[str, Dict[str, Any]]:
        return {
            agent_id: to_agent_card(profile)
            for agent_id, profile in self._agents.items()
            if isinstance(profile, dict)
        }

# Singleton instance
registry = AgentRegistry()

def register_agent(agent_id: str, profile: Optional[Dict[str, Any]] = None) -> None:
    registry.register_agent(agent_id, profile)

def unregister_agent(agent_id: str) -> None:
    registry.unregister_agent(agent_id)

def get_agent_profile(agent_id: str) -> Optional[Dict[str, Any]]:
    return registry.get_agent_profile(agent_id)

def list_agents() -> Dict[str, Dict[str, Any]]:
    return registry.list_agents()


def get_agent_card(agent_id: str) -> Optional[Dict[str, Any]]:
    return registry.get_agent_card(agent_id)


def list_agent_cards() -> Dict[str, Dict[str, Any]]:
    return registry.list_agent_cards()


def list_all_agents() -> Dict[str, Dict[str, Any]]:
    """Return all known agents as public agent cards (proprietary fields are hidden)."""
    combined: Dict[str, Dict[str, Any]] = {}

    try:
        from core.agents.master_agents import get_master_agent_manifest

        combined.update(get_master_agent_manifest())
    except Exception:
        # Keep runtime list available even if manifest import fails.
        pass

    for agent_id, profile in registry.list_agents().items():
        existing = combined.get(agent_id, {})
        merged = dict(existing)
        merged.update(profile or {})
        if "id" not in merged:
            merged["id"] = agent_id
        combined[agent_id] = to_agent_card(normalize_agent_profile(agent_id, merged))

    for agent_id, profile in list(combined.items()):
        if not isinstance(profile, dict):
            continue
        combined[agent_id] = to_agent_card(normalize_agent_profile(agent_id, profile))

    return combined