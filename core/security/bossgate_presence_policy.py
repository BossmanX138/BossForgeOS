from __future__ import annotations

import json
from pathlib import Path


class BossGatePresencePolicyStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> dict:
        if not self.path.exists():
            return {"accept_unknown_messages": False}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"accept_unknown_messages": False}
        if not isinstance(payload, dict):
            return {"accept_unknown_messages": False}
        return {"accept_unknown_messages": bool(payload.get("accept_unknown_messages", False))}

    def write(self, *, accept_unknown_messages: bool) -> dict:
        payload = {"accept_unknown_messages": bool(accept_unknown_messages)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
