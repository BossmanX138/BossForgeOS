"""
Agent Memory System — BossForgeOS

Provides persistent, dynamic memory for agents, including social logs, refusal, and retirement records.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

class AgentMemory:
    def __init__(self, agent_id: str, root: Path):
        self.agent_id = agent_id
        self.root = Path(root)
        self.memory_file = self.root / f"{agent_id}_memory.json"
        self._load()

    def _load(self):
        if self.memory_file.exists():
            self.data = json.loads(self.memory_file.read_text(encoding="utf-8"))
        else:
            self.data = {"events": [], "social_log": [], "refusals": [], "retirements": []}

    def save(self):
        self.memory_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def record_event(self, event: str, meta: Optional[Dict[str, Any]] = None):
        self.data["events"].append({"event": event, "meta": meta or {}, "ts": datetime.now().isoformat()})
        self.save()

    def add_social_log(self, agent: str, interaction: str):
        self.data["social_log"].append({"agent": agent, "interaction": interaction, "ts": datetime.now().isoformat()})
        self.save()

    def record_refusal(self, reason: str, context: Optional[Dict[str, Any]] = None):
        self.data["refusals"].append({"reason": reason, "context": context or {}, "ts": datetime.now().isoformat()})
        self.save()

    def retire_agent(self, agent: str, reason: str):
        self.data["retirements"].append({"agent": agent, "reason": reason, "ts": datetime.now().isoformat()})
        self.save()

    def compress(self):
        # Placeholder for future dynamic compression logic
        pass

    def archive(self):
        # Placeholder for archiving old memory
        pass
