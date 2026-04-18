from pathlib import Path
from typing import Any, Callable, Protocol

from core.rune.discovery_handoff import run_discovery_handoff
from core.rune.hands_on_runtime import auto_complete_discovery_items, run_hourly_discovery_cycle
from core.rune.rune_bus import RuneBus


class HandsOnRuntimeAdapter(Protocol):
    def handle_incoming_discovery(self, agent_id: str, args: dict[str, Any], root: Path) -> dict[str, Any]:
        ...

    def run_periodic_discovery(
        self,
        agent_id: str,
        root: Path,
        last_window_key: str | None,
        window_minutes: int = 2,
    ) -> dict[str, Any]:
        ...

    def auto_complete_discovery(
        self,
        agent_id: str,
        items: list[dict[str, Any]],
        save_items: Callable[[], None],
    ) -> dict[str, Any]:
        ...


class ForgeHandsOnAdapter:
    def __init__(self, bus: RuneBus) -> None:
        self.bus = bus

    def handle_incoming_discovery(self, agent_id: str, args: dict[str, Any], root: Path) -> dict[str, Any]:
        return run_discovery_handoff(self.bus, agent_id, args, root=root)

    def run_periodic_discovery(
        self,
        agent_id: str,
        root: Path,
        last_window_key: str | None,
        window_minutes: int = 2,
    ) -> dict[str, Any]:
        return run_hourly_discovery_cycle(
            bus=self.bus,
            agent_id=agent_id,
            root=root,
            last_window_key=last_window_key,
            window_minutes=window_minutes,
        )

    def auto_complete_discovery(
        self,
        agent_id: str,
        items: list[dict[str, Any]],
        save_items: Callable[[], None],
    ) -> dict[str, Any]:
        return auto_complete_discovery_items(
            bus=self.bus,
            agent_id=agent_id,
            items=items,
            save_items=save_items,
        )
