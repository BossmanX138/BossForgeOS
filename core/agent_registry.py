"""
Central Agent Registry for BossForgeOS
Provides a singleton registry for agent registration, discovery, and metadata lookup.
All agents should register themselves here at startup for unified orchestration.
"""
import threading
from typing import Any, Dict, Optional

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
        self._agents[agent_id] = profile or {}

    def unregister_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def get_agent_profile(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._agents)

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