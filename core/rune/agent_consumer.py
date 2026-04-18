import time
from collections.abc import Callable
from typing import Any

from core.rune.rune_bus import RuneBus


class AgentConsumerLoop:
    """Shared command consumer loop for bus-driven agents."""

    def __init__(
        self,
        bus: RuneBus,
        seen_commands: set[str],
        interval_seconds: float,
        on_idle: Callable[[], None] | None,
        on_command: Callable[[dict[str, Any]], None],
    ) -> None:
        self.bus = bus
        self.seen_commands = seen_commands
        self.interval_seconds = max(0.2, float(interval_seconds))
        self.on_idle = on_idle
        self.on_command = on_command

    def run(self, stop_check: Callable[[], bool]) -> None:
        while not stop_check():
            if self.on_idle is not None:
                self.on_idle()

            for _, payload in self.bus.poll_commands(self.seen_commands):
                self.on_command(payload)

            time.sleep(self.interval_seconds)
