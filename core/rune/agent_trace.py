"""Per-agent execution trace logging for BossForgeOS.

Records are written as timestamped JSON files under
``<bus_root>/bus/traces/<agent_id>/`` so they are co-located with the
rest of the bus data and can be inspected, archived, or pruned by the
Archivist in the same way as events and commands.

Usage::

    from core.rune.agent_trace import AgentTrace

    trace = AgentTrace("runeforge", bus_root=bus.root)
    path = trace.record("work_item", args={"title": "..."}, result={"ok": True}, duration_ms=42.1)
    recent = trace.read_recent(limit=10)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AgentTrace:
    """Writes structured execution trace records for a single agent.

    Each call to :meth:`record` produces one timestamped JSON file under
    ``<bus_root>/bus/traces/<agent_id>/``.
    """

    def __init__(self, agent_id: str, bus_root: Path) -> None:
        self.agent_id = str(agent_id).strip().lower()
        self.traces_dir = Path(bus_root) / "bus" / "traces" / self.agent_id
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        command: str,
        args: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        issued_by: str = "",
    ) -> Path:
        """Write a trace record and return its file path.

        Parameters
        ----------
        command:
            The command or event name being traced.
        args:
            Input arguments dict (copied as-is).
        result:
            Output/result dict (copied as-is).
        duration_ms:
            Elapsed wall-clock time in milliseconds, if known.
        issued_by:
            Who triggered the command (agent id, 'cli', 'voice', etc.).
        """
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%d_%H%M%S_%f")
        payload: dict[str, Any] = {
            "agent_id": self.agent_id,
            "command": str(command).strip(),
            "args": args if isinstance(args, dict) else {},
            "result": result if isinstance(result, dict) else {},
            "issued_by": str(issued_by).strip(),
            "timestamp": now.isoformat(),
        }
        if duration_ms is not None:
            payload["duration_ms"] = float(duration_ms)
        path = self.traces_dir / f"trace_{stamp}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def read_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent *limit* trace records, newest first."""
        limit = max(1, int(limit))
        records: list[dict[str, Any]] = []
        try:
            with os.scandir(self.traces_dir) as it:
                entries = sorted(
                    (e for e in it if e.is_file() and e.name.endswith(".json")),
                    key=lambda e: e.name,
                    reverse=True,
                )
        except OSError:
            return records
        for entry in entries[:limit]:
            try:
                data = json.loads(Path(entry.path).read_text(encoding="utf-8"))
                records.append(data if isinstance(data, dict) else {"raw": data})
            except (OSError, json.JSONDecodeError):
                continue
        return records
