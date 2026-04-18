from pathlib import Path
from typing import Any, Callable

from core.adapters.forge_hands_on_adapter import ForgeHandsOnAdapter, HandsOnRuntimeAdapter
from core.connectors.bossgate_connector import discover_transfer_targets
from core.rune.rune_bus import RuneBus


class BossGateHandsOnAdapter(HandsOnRuntimeAdapter):
    """
    BossGate-facing integration adapter for hands-on runtime concerns.

    Current behavior wraps ForgeHandsOnAdapter so agent behavior remains stable,
    while adding BossGate context/metadata for transport abstraction and future
    off-node routing.
    """

    def __init__(self, bus: RuneBus) -> None:
        self.bus = bus
        self._forge_fallback = ForgeHandsOnAdapter(bus)

    def _bossgate_context(self) -> dict[str, Any]:
        try:
            targets = discover_transfer_targets(timeout=0.2)
            return {
                "enabled": True,
                "discovered_targets": len(targets),
            }
        except Exception:
            return {
                "enabled": False,
                "discovered_targets": 0,
            }

    def handle_incoming_discovery(self, agent_id: str, args: dict[str, Any], root: Path) -> dict[str, Any]:
        result = self._forge_fallback.handle_incoming_discovery(agent_id=agent_id, args=args, root=root)
        if isinstance(result, dict):
            result.setdefault("integration", {})
            if isinstance(result["integration"], dict):
                result["integration"].update({"adapter": "bossgate", **self._bossgate_context()})
        return result

    def run_periodic_discovery(
        self,
        agent_id: str,
        root: Path,
        last_window_key: str | None,
        window_minutes: int = 2,
    ) -> dict[str, Any]:
        result = self._forge_fallback.run_periodic_discovery(
            agent_id=agent_id,
            root=root,
            last_window_key=last_window_key,
            window_minutes=window_minutes,
        )
        if isinstance(result, dict):
            result.setdefault("integration", {})
            if isinstance(result["integration"], dict):
                result["integration"].update({"adapter": "bossgate", **self._bossgate_context()})
        return result

    def auto_complete_discovery(
        self,
        agent_id: str,
        items: list[dict[str, Any]],
        save_items: Callable[[], None],
    ) -> dict[str, Any]:
        result = self._forge_fallback.auto_complete_discovery(
            agent_id=agent_id,
            items=items,
            save_items=save_items,
        )
        if isinstance(result, dict):
            result.setdefault("integration", {})
            if isinstance(result["integration"], dict):
                result["integration"].update({"adapter": "bossgate", **self._bossgate_context()})
        return result
